import logging
from typing import Any, Dict, Optional

from core.device import Device
from core.dlna_device import DLNADevice
from core.transcreen_device import TranscreenDevice

logger = logging.getLogger(__name__)


class DeviceLifecycleService:
    """
    Own runtime device registration, lookup, unregister, and core state cleanup.
    """

    def __init__(
        self,
        *,
        owner: Any,
        device_inventory,
        runtime_registry,
        playback_intent_service,
        playback_monitoring_service,
        device_state_lock,
        assignment_lock,
        acquire_device_lock,
        release_device_lock,
    ):
        self.owner = owner
        self.device_inventory = device_inventory
        self.runtime_registry = runtime_registry
        self.playback_intent_service = playback_intent_service
        self.playback_monitoring_service = playback_monitoring_service
        self.device_state_lock = device_state_lock
        self.assignment_lock = assignment_lock
        self.acquire_device_lock = acquire_device_lock
        self.release_device_lock = release_device_lock

    def get_devices(self):
        if not self.acquire_device_lock():
            return []
        try:
            return self.device_inventory.list_devices()
        finally:
            self.release_device_lock()

    def get_device(self, device_name: str) -> Optional[Device]:
        if not self.acquire_device_lock():
            return None
        try:
            return self.device_inventory.get(device_name)
        finally:
            self.release_device_lock()

    def register_device(self, device_info: Dict[str, Any]) -> Optional[Device]:
        try:
            device_name = device_info.get("device_name")
            device_type = device_info.get("type", "dlna")

            if not device_name:
                logger.error("Device missing name")
                return None

            if device_type == "dlna":
                device = DLNADevice(device_info)
            elif device_type == "transcreen":
                device = TranscreenDevice(device_info)
            else:
                logger.error("Unknown device type: %s", device_type)
                return None

            if hasattr(device, "device_manager"):
                device.device_manager = self.owner
            if hasattr(device, "runtime"):
                device.runtime = self.owner

            if not self.acquire_device_lock():
                return None

            try:
                existing_device = None
                if self.device_inventory.contains(device_name):
                    existing_device = self.device_inventory.get(device_name)
                    if (
                        existing_device.device_info.get("hostname") == device_info.get("hostname")
                        and existing_device.device_info.get("location") == device_info.get("location")
                    ):
                        logger.info("Device %s already registered with same parameters", device_name)
                        return existing_device

                    logger.info("Device %s already registered but with different parameters, updating", device_name)
                    if hasattr(existing_device, "streaming_url") and existing_device.streaming_url:
                        logger.info(
                            "Preserving streaming info during device update: %s:%s",
                            existing_device.streaming_url,
                            existing_device.streaming_port,
                        )
                        device.update_streaming_info(existing_device.streaming_url, existing_device.streaming_port)
                    if hasattr(existing_device, "is_playing") and existing_device.is_playing:
                        device.update_playing(True)
                        if hasattr(existing_device, "current_video"):
                            device.current_video = existing_device.current_video

                self.device_inventory.set(device_name, device)
                logger.info("Registered %s device: %s", device_type, device_name)
            finally:
                self.release_device_lock()

            with self.device_state_lock:
                if device_name not in self.runtime_registry.device_status:
                    self.runtime_registry.ensure_device(device_name)
                    logger.info("Initialized device_status for %s", device_name)
                if device_name not in self.runtime_registry.last_seen:
                    self.runtime_registry.mark_seen(device_name)

            return device
        except Exception as exc:
            logger.error("Error registering device: %s", exc)
            return None

    def cleanup_device_state(self, device_name: str) -> None:
        logger.info("Cleaning up state for device %s", device_name)
        self.playback_monitoring_service.stop_health_check(device_name)

        with self.device_state_lock:
            if self.playback_intent_service.get_assigned_video(device_name):
                logger.info("Clearing assigned video for device %s", device_name)
                self.playback_intent_service.clear_assigned_video(device_name)

        if device_name in self.playback_intent_service.video_assignment_priority:
            logger.info("Clearing video assignment priority for device %s", device_name)
            self.playback_intent_service.clear_priority(device_name)

        if device_name in self.playback_intent_service.device_assignment_queue:
            logger.info("Clearing device from assignment queue: %s", device_name)
            self.playback_intent_service.clear_assignment_queue(device_name)

    def unregister_device(self, device_name: str) -> bool:
        if not self.device_state_lock.acquire(blocking=True, timeout=self.owner.device_lock_timeout):
            return False

        try:
            if not self.device_inventory.contains(device_name):
                logger.warning("Device not found: %s", device_name)
                return False

            self.device_inventory.remove(device_name)
            self.runtime_registry.remove_device(device_name)
            if self.playback_intent_service.get_assigned_video(device_name) is not None:
                self.playback_intent_service.clear_assigned_video(device_name)

            with self.assignment_lock:
                self.playback_intent_service.clear_device(device_name)

            self.playback_monitoring_service.clear_device_state(device_name)
            logger.info("Unregistered device: %s", device_name)
            return True
        finally:
            try:
                self.device_state_lock.release()
            except RuntimeError:
                pass

    def update_device_playing_state(self, device_name: str, is_playing: bool, video_path: str = None) -> None:
        device = self.get_device(device_name)
        if not device:
            return

        with self.device_state_lock:
            device.update_playing(is_playing)
            if video_path:
                device.current_video = video_path
            self.runtime_registry.update_playing_state(device_name, is_playing, video_path)
