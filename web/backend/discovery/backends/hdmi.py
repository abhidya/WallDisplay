"""
HDMI/local projector discovery backend.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from web.backend.core.renderer_service.service import RendererService

from ..base import CastingSession, Device, DeviceCapability, DiscoveryBackend, CastingMethod

logger = logging.getLogger(__name__)


class HDMIDiscoveryBackend(DiscoveryBackend):
    """Discover and cast to renderer-configured local HDMI projectors."""

    def __init__(self, renderer_service: Optional[Any] = None):
        super().__init__("HDMI", CastingMethod.HDMI)
        self.renderer_service = renderer_service or RendererService()

    async def discover_devices(self) -> List[Device]:
        devices: List[Device] = []
        for projector in self.renderer_service.list_projectors():
            if projector.get("sender") != "hdmi":
                continue
            devices.append(self._device_from_projector(projector))
        return devices

    async def cast_content(
        self,
        device: Device,
        content_url: str,
        content_type: str = "video/mp4",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CastingSession:
        if device.casting_method != CastingMethod.HDMI:
            raise ValueError(f"Device {device.name} is not an HDMI device")

        projector_id = device.metadata.get("renderer_projector_id") or device.id
        content_mode = (metadata or {}).get("content_mode") or "url"
        if not self.renderer_service.start_projector_url(
            projector_id,
            content_url,
            content_mode=content_mode,
            options=metadata or {},
        ):
            raise RuntimeError(f"Failed to cast content to HDMI projector {projector_id}")

        session = CastingSession(
            id=str(uuid.uuid4()),
            device=device,
            content_url=content_url,
            content_type=content_type,
            metadata=metadata or {},
        )
        self.active_sessions[session.id] = session
        return session

    async def stop_casting(self, session: CastingSession) -> bool:
        projector_id = session.device.metadata.get("renderer_projector_id") or session.device.id
        success = self.renderer_service.stop_renderer(projector_id)
        if success:
            session.is_active = False
            self.active_sessions.pop(session.id, None)
        return success

    async def pause_casting(self, session: CastingSession) -> bool:
        session.is_paused = True
        return False

    async def resume_casting(self, session: CastingSession) -> bool:
        session.is_paused = False
        return False

    async def seek(self, session: CastingSession, position: float) -> bool:
        session.position = position
        return False

    async def get_status(self, session: CastingSession) -> Dict[str, Any]:
        projector_id = session.device.metadata.get("renderer_projector_id") or session.device.id
        status = self.renderer_service.get_renderer_status(projector_id)
        return {
            "is_active": session.is_active,
            "is_paused": session.is_paused,
            "content_url": session.content_url,
            "device": session.device.name,
            "created_at": session.started_at.isoformat(),
            "renderer_status": status,
        }

    def _device_from_projector(self, projector: Dict[str, Any]) -> Device:
        runtime_status = projector.get("runtime_status") or {}
        sender_status = runtime_status.get("sender_status") or {}
        display = sender_status.get("display") or {}
        target_name = projector.get("target_name") or sender_status.get("target") or ""
        connection_state = sender_status.get("connection_state") or "detached"
        width = int(display.get("width") or 0)
        height = int(display.get("height") or 0)
        resolution = (width, height) if width and height else None

        metadata = {
            "renderer_projector_id": projector["id"],
            "target_name": target_name,
            "connection_state": connection_state,
            "projection_state": sender_status.get("projection_state", "idle"),
            "power_state": sender_status.get("power_state", "unknown"),
            "display": display or None,
            "managed_by": "renderer_config",
        }

        device = Device(
            id=projector["id"],
            name=projector["id"],
            friendly_name=projector.get("name") or projector["id"],
            casting_method=CastingMethod.HDMI,
            hostname=target_name or "localhost",
            port=0,
            capabilities=[
                DeviceCapability.WEB_CONTENT,
                DeviceCapability.VIDEO_PLAYBACK,
                DeviceCapability.IMAGE_DISPLAY,
                DeviceCapability.SCREEN_MIRRORING,
            ],
            metadata=metadata,
            display_index=display.get("index"),
            resolution=resolution,
            is_online=connection_state == "attached",
        )
        device.last_seen = datetime.now()
        return device
