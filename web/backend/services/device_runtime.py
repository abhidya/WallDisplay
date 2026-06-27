import os
from contextlib import nullcontext
from typing import Any, Optional


class DeviceRuntimeModule:
    """
    Deep interface for runtime device operations.

    AppRuntime remains the compatibility facade, but new callers should use this
    module instead of reaching across AppRuntime for discovery, inventory, and
    playback details.
    """

    def __init__(self, owner: Any):
        self.owner = owner
        self._resolving_owner_get_device = False

    @property
    def discovery_manager(self):
        return self.owner.discovery_manager

    @property
    def discovery_authority(self) -> str:
        authority = os.environ.get("NANODLNA_DISCOVERY_AUTHORITY", "legacy").strip().lower()
        return authority if authority in {"legacy", "unified"} else "legacy"

    @property
    def uses_unified_discovery_authority(self) -> bool:
        return self.discovery_authority == "unified"

    def _get_discovery_controller(self):
        discovery_coordinator = getattr(self.owner, "discovery_coordinator", None)
        if discovery_coordinator is not None:
            return discovery_coordinator
        device_manager = getattr(self.owner, "device_manager", None)
        return getattr(device_manager, "discovery_coordinator", device_manager)

    def _get_active_discovery_controller(self):
        if self.uses_unified_discovery_authority:
            return self.owner.unified_discovery_lifecycle_service
        return self._get_discovery_controller()

    def start_discovery(self) -> None:
        self._get_active_discovery_controller().start()

    def stop_discovery(self) -> None:
        self._get_active_discovery_controller().stop()

    def pause_discovery(self) -> None:
        self._get_active_discovery_controller().pause()

    def resume_discovery(self) -> None:
        self._get_active_discovery_controller().resume()

    def set_discovery_interval(self, seconds: int) -> int:
        if seconds < 1:
            raise ValueError("Discovery interval must be at least 1 second")

        if self.uses_unified_discovery_authority:
            backends = getattr(self.discovery_manager, "backends", {}) if self.discovery_manager is not None else {}
            for backend in backends.values():
                if hasattr(backend, "discovery_interval"):
                    backend.discovery_interval = seconds
        else:
            discovery_controller = self._get_discovery_controller()
            manager = getattr(discovery_controller, "manager", getattr(self.owner, "device_manager", None))
            if manager is None:
                raise RuntimeError("Legacy discovery manager is unavailable")
            manager.discovery_interval = seconds

        return seconds

    def get_discovery_status(self) -> dict:
        status = self._get_active_discovery_controller().get_status()
        status["authority"] = self.discovery_authority
        status["unified_running"] = getattr(
            getattr(self.owner, "unified_discovery_lifecycle_service", None),
            "is_running",
            getattr(getattr(self.owner, "discovery_manager", None), "is_running", False),
        )
        return status

    def get_devices(self):
        lifecycle = getattr(self.owner, "device_lifecycle_service", None)
        if lifecycle is not None:
            return lifecycle.get_devices()
        inventory = getattr(self.owner, "device_inventory_service", None)
        return inventory.list_devices() if inventory is not None else []

    def get_device_items(self):
        return list(self.owner.device_inventory_service.items())

    def get_device_count(self) -> int:
        return len(self.owner.device_inventory_service.devices)

    def get_playing_device_count(self) -> int:
        return sum(
            1
            for device in self.owner.device_inventory_service.values()
            if getattr(device, "is_playing", False)
        )

    def get_device(self, device_name: str):
        lifecycle = getattr(self.owner, "device_lifecycle_service", None)
        if lifecycle is not None:
            return lifecycle.get_device(device_name)
        inventory = getattr(self.owner, "device_inventory_service", None)
        if inventory is not None:
            return inventory.get(device_name)
        owner_get_device = getattr(self.owner, "get_device", None)
        if owner_get_device is not None and not self._resolving_owner_get_device:
            self._resolving_owner_get_device = True
            try:
                return owner_get_device(device_name)
            finally:
                self._resolving_owner_get_device = False
        return None

    def register_device(self, device_info: dict):
        lifecycle = getattr(self.owner, "device_lifecycle_service", None)
        return lifecycle.register_device(device_info) if lifecycle is not None else None

    def unregister_device(self, device_name: str) -> bool:
        lifecycle = getattr(self.owner, "device_lifecycle_service", None)
        return lifecycle.unregister_device(device_name) if lifecycle is not None else False

    def cleanup_device_state(self, device_name: str) -> None:
        lifecycle = getattr(self.owner, "device_lifecycle_service", None)
        if lifecycle is not None:
            lifecycle.cleanup_device_state(device_name)

    def update_device_status(
        self,
        *,
        device_name: str,
        status: str,
        is_playing=None,
        current_video=None,
        error=None,
    ) -> None:
        with self.owner.device_state_lock:
            self.owner.runtime_registry_service.update_status(
                device_name=device_name,
                status=status,
                is_playing=is_playing,
                current_video=current_video,
                error=error,
            )

    def auto_play_video(self, device, video_path: str, loop: bool = True, config=None) -> bool:
        return self.owner.auto_play_video(device, video_path, loop=loop, config=config)

    def start_playback_health_check(self, device_name: str, video_path: str) -> None:
        playback_monitoring = getattr(self.owner, "playback_monitoring_service", None)
        if playback_monitoring is not None:
            playback_monitoring.start_health_check(device_name, video_path)

    def stop_playback_health_check(self, device_name: str) -> None:
        playback_monitoring = getattr(self.owner, "playback_monitoring_service", None)
        if playback_monitoring is not None:
            playback_monitoring.stop_health_check(device_name)

    def track_playback_result(self, device_name: str, video_path: str, success: bool) -> None:
        playback_monitoring = getattr(self.owner, "playback_monitoring_service", None)
        if playback_monitoring is not None:
            playback_monitoring.track_playback_result(device_name, video_path, success)

    def get_device_playback_stats(self, device_name: str) -> dict:
        playback_monitoring = getattr(self.owner, "playback_monitoring_service", None)
        if playback_monitoring is not None:
            return playback_monitoring.get_device_playback_stats(device_name)
        return {
            "attempts": 0,
            "successes": 0,
            "success_rate": 0,
            "last_attempt": None,
            "videos": {},
        }

    def save_devices_to_config(self, config_file: str) -> bool:
        try:
            abs_path = os.path.abspath(config_file)
            device_lock = getattr(self.owner, "device_state_lock", None)
            lock_context = device_lock if device_lock is not None else nullcontext()

            with lock_context:
                devices_config = [
                    getattr(device, "device_info", {}).copy()
                    for device in self.owner.device_inventory_service.values()
                ]

            import json

            with open(abs_path, "w") as file_handle:
                json.dump(devices_config, file_handle, indent=4)

            return True
        except Exception:
            return False

    def update_runtime_playback_progress(
        self,
        device_name: str,
        position: str,
        duration: str,
        progress: int,
    ) -> None:
        with self.owner.device_state_lock:
            self.owner.runtime_registry_service.update_playback_progress(
                device_name,
                position,
                duration,
                progress,
            )

    def update_device_playback_progress(
        self,
        device_name: str,
        position: str,
        duration: str,
        progress: int,
    ) -> None:
        if not hasattr(self.owner, "device_state_lock") and hasattr(self.owner, "update_runtime_playback_progress"):
            self.owner.update_runtime_playback_progress(device_name, position, duration, progress)
        else:
            self.update_runtime_playback_progress(device_name, position, duration, progress)
        device = self.get_device(device_name)
        if (
            device
            and hasattr(device, "current_position")
            and hasattr(device, "duration_formatted")
            and hasattr(device, "playback_progress")
        ):
            device.current_position = position
            device.duration_formatted = duration
            device.playback_progress = progress

    def discover_dlna_devices(self, timeout: float):
        if self.uses_unified_discovery_authority:
            unified_discover = getattr(self.owner, "_discover_dlna_devices_via_unified", None)
            if unified_discover is not None:
                return unified_discover(timeout)
            return self._discover_dlna_devices_via_unified(timeout)
        return self._get_discovery_controller().discover_dlna_devices(timeout=timeout)

    def _discover_dlna_devices_via_unified(self, timeout: float):
        import asyncio

        async def _run():
            devices = await self.discovery_manager.discover_devices(
                backend_name="dlna",
                timeout=max(int(timeout), 1),
            )
            return [
                {
                    "device_name": device.friendly_name or device.name,
                    "name": device.name,
                    "type": "dlna",
                    "friendly_name": device.friendly_name or device.name,
                    "hostname": device.hostname,
                    "action_url": device.action_url,
                    "manufacturer": device.manufacturer,
                    "location": device.location,
                }
                for device in devices
            ]

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(_run())

        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run())
        finally:
            loop.close()

    def get_assigned_video(self, device_name: str):
        return self.owner.playback_intent_service.get_assigned_video(device_name)
