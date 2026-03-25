import json
import logging
import os
import traceback
from typing import Any, Callable, Dict, List

from core.config_service import ConfigService
from core.streaming_registry import StreamingSessionRegistry
from models.device import DeviceModel

logger = logging.getLogger(__name__)


class DeviceDiscoveryService:
    """
    Own discovery/config synchronization flows that were previously implemented inline in DeviceService.
    """

    def __init__(
        self,
        *,
        db,
        runtime,
        runtime_sync_service,
        get_device_by_name: Callable[[str], DeviceModel | None],
        update_device_status: Callable[[str, str, bool], bool],
    ):
        self.db = db
        self.runtime = runtime
        self.runtime_sync_service = runtime_sync_service
        self.get_device_by_name = get_device_by_name
        self.update_device_status = update_device_status

    def discover_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        try:
            logger.debug(f"Starting device discovery with timeout {timeout} seconds")
            discovered_devices = self.runtime_sync_service.discover_dlna_devices(timeout=timeout)
            logger.debug(f"Discovered devices: {discovered_devices}")

            existing_devices = {}
            for db_device in self.db.query(DeviceModel).all():
                existing_devices[db_device.name] = {
                    "db_device": db_device,
                    "core_device": self.runtime_sync_service.get_core_device(db_device.name),
                }

            streaming_registry = StreamingSessionRegistry.get_instance()
            active_streaming_devices = set()
            try:
                for session in streaming_registry.get_active_sessions():
                    active_streaming_devices.add(session.device_name)
                    logger.info(
                        "Device %s has active streaming sessions, skipping auto-play",
                        session.device_name,
                    )
            except Exception as exc:
                logger.error(f"Error checking streaming registry: {exc}")
                logger.exception("Detailed streaming registry error:")

            db_devices = []
            discovered_names = set()

            for device_info in discovered_devices:
                device_name = (
                    device_info.get("friendly_name")
                    or device_info.get("name")
                    or device_info.get("device_name")
                )
                logger.info(f"Processing discovered device: {device_name}")
                discovered_names.add(device_name)

                device_info["device_name"] = device_name
                device_info["name"] = device_name
                device_info["type"] = "dlna"

                existing_data = existing_devices.get(device_name)
                if existing_data:
                    db_device = existing_data["db_device"]
                    core_device = existing_data["core_device"]

                    logger.info(
                        "Device %s already exists in database, updating status only",
                        device_name,
                    )
                    db_device.status = "connected"
                    self.db.commit()
                    self.db.refresh(db_device)

                    is_already_playing = False
                    if device_name in active_streaming_devices:
                        is_already_playing = True
                        logger.info(f"Device {device_name} has active streaming sessions")
                    if core_device and core_device.is_playing:
                        is_already_playing = True
                        logger.info(f"Device {device_name} reports is_playing=True")
                    if db_device.is_playing:
                        is_already_playing = True
                        logger.info(f"Database shows device {device_name} is_playing=True")
                    if db_device.current_video:
                        is_already_playing = True
                        logger.info(
                            "Device %s has current_video=%s",
                            device_name,
                            db_device.current_video,
                        )

                    if is_already_playing:
                        db_device.is_playing = True
                        self.db.commit()
                        logger.info(f"Updated device {device_name} playing status")

                    db_devices.append(db_device)
                    continue

                logger.info(f"Creating new device {device_name} in database")
                db_device = DeviceModel(
                    name=device_name,
                    type=device_info.get("type", "dlna"),
                    hostname=device_info.get("hostname", ""),
                    action_url=device_info.get("action_url", ""),
                    friendly_name=device_info.get("friendly_name", device_name),
                    manufacturer=device_info.get("manufacturer", ""),
                    location=device_info.get("location", ""),
                    status="connected",
                    is_playing=False,
                    config=device_info,
                )
                self.db.add(db_device)
                self.db.commit()
                self.db.refresh(db_device)

                core_device = self.runtime_sync_service.register(device_info)
                device_config = ConfigService.get_instance().get_device_config(device_name)
                if device_config and "video_file" in device_config:
                    video_path = device_config["video_file"]
                    if os.path.exists(video_path):
                        logger.info(
                            "Auto-playing video %s on new device %s",
                            video_path,
                            device_name,
                        )
                        if core_device:
                            success = self.runtime.auto_play_video(
                                core_device,
                                video_path,
                                loop=True,
                            )
                            if success:
                                db_device.status = "connected"
                                db_device.is_playing = True
                                db_device.current_video = video_path
                                self.db.commit()
                                logger.info(
                                    "Updated device %s status in database",
                                    device_name,
                                )
                    else:
                        logger.error(f"Video file not found: {video_path}")

                db_devices.append(db_device)

            self.sync_device_status_with_discovery(discovered_names)

            result = []
            for device in db_devices:
                device_dict = device.to_dict()
                if "name" not in device_dict and "friendly_name" in device_dict:
                    device_dict["name"] = device_dict["friendly_name"]
                result.append(device_dict)
            return result
        except Exception as exc:
            logger.error(f"Error discovering devices: {exc}")
            traceback.print_exc()
            return []

    def load_devices_from_config(self, config_file: str) -> List[Dict[str, Any]]:
        try:
            abs_path = os.path.abspath(config_file)
            logger.info(f"Loading devices from config file: {abs_path}")

            with open(abs_path, "r") as file_handle:
                config_data = json.load(file_handle)

            devices_config = config_data["devices"] if "devices" in config_data else config_data
            logger.info(f"Found {len(devices_config)} devices in config file")

            config_dir = os.path.dirname(abs_path)
            db_devices = []
            for device_info in devices_config:
                device_info = dict(device_info)
                device_name = device_info.get("device_name") or device_info.get("name")
                if not device_name:
                    logger.error("Device missing 'device_name' or 'name' in config file entry")
                    continue

                video_file = device_info.get("video_file")
                if video_file:
                    resolved_video_file = os.path.expanduser(os.path.expandvars(video_file))
                    if not os.path.isabs(resolved_video_file):
                        resolved_video_file = os.path.abspath(
                            os.path.join(config_dir, resolved_video_file)
                        )
                    device_info["video_file"] = resolved_video_file

                if "name" in device_info and "device_name" not in device_info:
                    device_info["device_name"] = device_name

                db_device = self.get_device_by_name(device_name)
                if db_device:
                    logger.info(f"Device {device_name} already exists in database, updating")
                    for key, value in device_info.items():
                        if hasattr(db_device, key):
                            setattr(db_device, key, value)

                    db_device.status = "disconnected"
                    db_device.config = device_info.get("config")
                    self.db.commit()
                    self.db.refresh(db_device)
                    db_devices.append(db_device)
                else:
                    logger.info(f"Creating new device {device_name} in database")
                    db_device = DeviceModel(
                        name=device_name,
                        type=device_info.get("type", "dlna"),
                        hostname=device_info.get("hostname", ""),
                        action_url=device_info.get("action_url", ""),
                        friendly_name=device_info.get("friendly_name", device_name),
                        manufacturer=device_info.get("manufacturer", ""),
                        location=device_info.get("location", ""),
                        status="disconnected",
                        is_playing=False,
                        config=device_info.get("config"),
                    )
                    self.db.add(db_device)
                    self.db.commit()
                    self.db.refresh(db_device)
                    db_devices.append(db_device)

                self.runtime_sync_service.register_and_update(
                    device_info,
                    status="disconnected",
                )

            return [device.to_dict() for device in db_devices]
        except Exception as exc:
            self.db.rollback()
            logger.error(f"Error loading devices from config: {exc}")
            return []

    def save_devices_to_config(self, config_file: str) -> bool:
        try:
            return self.runtime.save_devices_to_config(config_file)
        except Exception as exc:
            logger.error(f"Error saving devices to config: {exc}")
            return False

    def sync_device_status_with_discovery(self, discovered_device_names: set) -> None:
        all_devices = self.db.query(DeviceModel).all()
        for device in all_devices:
            if device.name not in discovered_device_names:
                self.update_device_status(device.name, "disconnected", is_playing=False)
                continue

            core_device = self.runtime_sync_service.get_core_device(device.name)
            is_playing = False
            if core_device and core_device.is_playing:
                is_playing = True
            elif device.is_playing:
                is_playing = True
            elif device.current_video:
                is_playing = True

            self.update_device_status(device.name, "connected", is_playing=is_playing)
