from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from web.backend.core.overlay_window_url import build_overlay_window_url
from web.backend.services.overlay_cast_service import get_overlay_cast_pipeline
from web.backend.services.overlay_event_bus import notify_overlay_config_update
from web.backend.services.overlay_service import OverlayService


class SceneProjectionService:
    """Launch mapping scenes through the overlay runtime onto concrete projector transports."""

    def __init__(self, db: Session, renderer_service: Optional[Any] = None, overlay_cast_pipeline: Optional[Any] = None):
        self.db = db
        self.renderer_service = renderer_service
        self.overlay_cast_pipeline = overlay_cast_pipeline

    def ensure_overlay_config(self, scene_id: int) -> Dict[str, Any]:
        overlay_service = OverlayService(self.db)
        config = overlay_service.get_or_create_mapping_config(scene_id)
        notify_overlay_config_update([config.id], "scene_projection_config_ready")
        return config.model_dump(mode="json")

    async def launch(
        self,
        scene_id: int,
        *,
        target_type: str,
        target_id: str,
        overlay_base_url: str,
        controls_hidden: bool = True,
    ) -> Dict[str, Any]:
        target_type = str(target_type or "").lower()
        target_id = str(target_id or "").strip()
        if target_type not in {"hdmi", "dlna"}:
            raise ValueError("target_type must be hdmi or dlna")
        if not target_id:
            raise ValueError("target_id is required")

        config = self.ensure_overlay_config(scene_id)
        config_id = int(config["id"])

        if target_type == "hdmi":
            renderer_service = self.renderer_service or self._get_renderer_service()
            launch_options = {
                "config_id": config_id,
                "controls": "hidden" if controls_hidden else "visible",
                "projection_mode": "1",
            }
            overlay_url = build_overlay_window_url(
                overlay_base_url,
                config_id=config_id,
                controls_hidden=controls_hidden,
                projector_id=target_id,
                mode="overlay",
                extra_params={"projection_mode": "1"},
            )
            ok = renderer_service.start_projector_url(
                target_id,
                overlay_url,
                content_mode="overlay",
                options=launch_options,
            )
            if not ok:
                raise RuntimeError(f"Failed to launch mapping scene {scene_id} on HDMI projector {target_id}")
            return {
                "status": "launched",
                "transport": "hdmi",
                "target_id": target_id,
                "scene_id": int(scene_id),
                "overlay_config": config,
                "renderer_status": renderer_service.get_renderer_status(target_id),
            }

        cast_pipeline = self.overlay_cast_pipeline or get_overlay_cast_pipeline()
        cast_session = await cast_pipeline.start_cast(
            device_id=target_id,
            config_id=config_id,
            overlay_base_url=overlay_base_url,
            controls_hidden=controls_hidden,
        )
        return {
            "status": "launched",
            "transport": "dlna",
            "target_id": target_id,
            "scene_id": int(scene_id),
            "overlay_config": config,
            "cast_session": cast_session,
        }

    async def stop(self, *, target_type: str, target_id: str) -> Dict[str, Any]:
        target_type = str(target_type or "").lower()
        target_id = str(target_id or "").strip()
        if not target_id:
            raise ValueError("target_id is required")
        if target_type == "hdmi":
            renderer_service = self.renderer_service or self._get_renderer_service()
            stopped = renderer_service.stop_renderer(target_id)
            return {"status": "stopped" if stopped else "not_stopped", "transport": "hdmi", "target_id": target_id}
        if target_type == "dlna":
            cast_pipeline = self.overlay_cast_pipeline or get_overlay_cast_pipeline()
            stopped = await cast_pipeline.stop_cast(target_id)
            return {"status": "stopped" if stopped else "not_found", "transport": "dlna", "target_id": target_id}
        raise ValueError("target_type must be hdmi or dlna")

    @staticmethod
    def _get_renderer_service():
        from web.backend.routers.renderer_router import get_renderer_service

        return get_renderer_service()
