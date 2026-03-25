import logging
from typing import Any, Dict, Optional

from models.device import DeviceModel

logger = logging.getLogger(__name__)


class DeviceRuntimeSyncService:
    """
    Synchronize persisted device records with the live runtime device registry.
    """

    def __init__(self, runtime):
        self.runtime = runtime

    def build_device_info(self, device: Any) -> Dict[str, Any]:
        if isinstance(device, dict):
            device_name = device.get("device_name") or device.get("name")
            device_info = {
                "device_name": device_name,
                "type": device.get("type", "dlna"),
                "hostname": device.get("hostname", ""),
                "action_url": device.get("action_url", ""),
                "friendly_name": device.get("friendly_name", device_name),
                "manufacturer": device.get("manufacturer", ""),
                "location": device.get("location", ""),
            }
            if device.get("config"):
                device_info.update(device["config"])
            return device_info

        if isinstance(device, DeviceModel) or hasattr(device, "name"):
            device_info = {
                "device_name": device.name,
                "type": device.type,
                "hostname": device.hostname,
                "action_url": device.action_url,
                "friendly_name": device.friendly_name,
                "manufacturer": device.manufacturer,
                "location": device.location,
            }
            if device.config:
                device_info.update(device.config)
            return device_info

        raise TypeError(f"Unsupported device type for runtime sync: {type(device)}")

    def register(self, device: Any):
        return self.runtime.register_device(self.build_device_info(device))

    def unregister(self, device_name: str) -> bool:
        return self.runtime.unregister_device(device_name)

    def update_status(
        self,
        *,
        device_name: str,
        status: str,
        is_playing: Optional[bool] = None,
        current_video: Optional[str] = None,
    ) -> None:
        self.runtime.update_device_status(
            device_name=device_name,
            status=status,
            is_playing=is_playing,
            current_video=current_video,
        )

    def register_and_update(
        self,
        device: Any,
        *,
        status: str,
        is_playing: Optional[bool] = None,
        current_video: Optional[str] = None,
    ):
        registered = self.register(device)
        device_name = device.get("device_name") if isinstance(device, dict) else device.name
        self.update_status(
            device_name=device_name,
            status=status,
            is_playing=is_playing,
            current_video=current_video,
        )
        return registered

    def get_core_device(self, device_name: str):
        return self.runtime.get_device(device_name)

    def get_or_register_core_device(self, device: DeviceModel):
        core_device = self.runtime.get_device(device.name)
        if core_device:
            return core_device

        logger.debug("Registering runtime device from DB record: %s", device.name)
        return self.register(device)

    def discover_dlna_devices(self, timeout: float):
        return self.runtime.discover_dlna_devices(timeout=timeout)
