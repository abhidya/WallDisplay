import logging
from typing import Any, Dict, List, Optional

from web.backend.core.renderer_service.service import RendererService
from web.backend.models.device import DeviceModel

logger = logging.getLogger(__name__)


def get_default_renderer_service():
    try:
        from web.backend.routers.renderer_router import get_renderer_service

        return get_renderer_service()
    except Exception:
        return RendererService()


class HDMIDeviceSyncService:
    """
    Synchronize renderer-configured HDMI projectors into the persisted Devices inventory.
    """

    def __init__(self, db, runtime, renderer_service: Optional[Any] = None):
        self.db = db
        self.runtime = runtime
        self.renderer_service = renderer_service

    def sync_configured_projectors(self) -> List[DeviceModel]:
        renderer_service = self.renderer_service or get_default_renderer_service()
        synced_devices: List[DeviceModel] = []
        for projector in renderer_service.list_projectors():
            if projector.get("sender") != "hdmi":
                continue
            synced_devices.append(self._sync_projector(projector))
        return synced_devices

    def _sync_projector(self, projector: Dict[str, Any]) -> DeviceModel:
        projector_id = projector["id"]
        runtime_status = projector.get("runtime_status") or {}
        sender_status = runtime_status.get("sender_status") or {}
        target_name = projector.get("target_name") or sender_status.get("target") or ""
        display = sender_status.get("display")
        connection_state = sender_status.get("connection_state") or "detached"
        projection_state = sender_status.get("projection_state") or "idle"
        is_attached = connection_state == "attached"

        config = {
            "device_name": projector_id,
            "name": projector_id,
            "type": "hdmi",
            "casting_method": "hdmi",
            "managed_by": "renderer_config",
            "renderer_projector_id": projector_id,
            "target_name": target_name,
            "content_modes": projector.get("content_modes", []),
            "power_state": sender_status.get("power_state", "unknown"),
            "connection_state": connection_state,
            "projection_state": projection_state,
        }
        if display:
            config["display"] = display

        db_device = self.db.query(DeviceModel).filter(DeviceModel.name == projector_id).first()
        if db_device is None:
            db_device = DeviceModel(
                name=projector_id,
                type="hdmi",
                hostname=target_name,
                action_url=None,
                friendly_name=projector.get("name") or projector_id,
                manufacturer="Local HDMI",
                location=f"renderer://projectors/{projector_id}",
                status="connected" if is_attached else "disconnected",
                is_playing=projection_state == "projecting",
                current_video=sender_status.get("content_url"),
                config=config,
            )
            self.db.add(db_device)
        else:
            db_device.type = "hdmi"
            db_device.hostname = target_name
            db_device.friendly_name = projector.get("name") or db_device.friendly_name or projector_id
            db_device.manufacturer = db_device.manufacturer or "Local HDMI"
            db_device.location = f"renderer://projectors/{projector_id}"
            db_device.status = "connected" if is_attached else "disconnected"
            db_device.is_playing = projection_state == "projecting"
            db_device.current_video = sender_status.get("content_url")
            db_device.config = config

        self.db.commit()
        self.db.refresh(db_device)
        self._update_runtime_state(db_device, is_attached, projection_state, sender_status.get("content_url"))
        return db_device

    def _update_runtime_state(
        self,
        db_device: DeviceModel,
        is_attached: bool,
        projection_state: str,
        current_video: Optional[str],
    ) -> None:
        status = "connected" if is_attached else "disconnected"
        is_playing = projection_state == "projecting"
        try:
            self.runtime.update_device_status(
                device_name=db_device.name,
                status=status,
                is_playing=is_playing,
                current_video=current_video,
            )
        except Exception as exc:
            logger.warning("Failed to update HDMI runtime status for %s: %s", db_device.name, exc)
