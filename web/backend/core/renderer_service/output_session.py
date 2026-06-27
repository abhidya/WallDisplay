import logging
from typing import Any, Callable, Dict, Optional
from urllib.parse import urlencode

from web.backend.core.overlay_window_url import build_overlay_window_url

from .sender.hdmi import HDMISender


class ProjectorOutputSession:
    """Own one local HDMI projector output session behind a small interface."""

    def __init__(
        self,
        projector_id: str,
        projector_config: Dict[str, Any],
        *,
        sender_factory: Callable[[], HDMISender],
        server_base_url: str,
        logger: Optional[logging.Logger] = None,
    ):
        self.projector_id = projector_id
        self.projector_config = projector_config
        self.sender_factory = sender_factory
        self.server_base_url = server_base_url.rstrip("/")
        self.logger = logger or logging.getLogger(__name__)
        self.sender: Optional[HDMISender] = None
        self.scene_id: Optional[str] = None
        self.content_mode: Optional[str] = None
        self.options: Dict[str, Any] = {}

    @classmethod
    def idle_status(
        cls,
        projector_id: str,
        projector: Dict[str, Any],
        *,
        display_finder: Callable[[Optional[str]], Optional[Dict[str, Any]]],
        power_state: str = "unknown",
    ) -> Dict[str, Any]:
        target_name = projector.get("target_name")
        display = display_finder(target_name)
        sender_status = {
            "type": "hdmi",
            "target": target_name,
            "connection_state": "attached" if display else "detached",
            "projection_state": "idle",
            "power_state": power_state,
            "process_running": False,
            "content_url": None,
            "last_error": None,
            "last_heartbeat_at": None,
        }
        if display:
            sender_status["display"] = display
        return {
            "projector_id": projector_id,
            "sender_type": "hdmi",
            "target_name": target_name,
            "content_mode": None,
            "options": {},
            "status": "idle",
            "sender_status": sender_status,
        }

    def start_url(
        self,
        content_url: str,
        *,
        content_mode: str = "url",
        options: Optional[Dict[str, Any]] = None,
        scene_id: Optional[str] = None,
    ) -> bool:
        target_name = self.projector_config.get("target_name")
        if not target_name:
            self.logger.error("No target name specified for HDMI projector %s", self.projector_id)
            return False

        sender = self.sender_factory()
        if not sender.connect(target_name):
            return False
        if not sender.send_content(content_url):
            sender.disconnect()
            return False

        self.stop()
        self.sender = sender
        self.scene_id = scene_id
        self.content_mode = content_mode
        self.options = options or {}
        return True

    def start_mode(self, mode: str, options: Optional[Dict[str, Any]] = None) -> bool:
        if mode == "scene":
            self.logger.error("Scene mode requires caller-rendered content")
            return False
        content_url = self.content_mode_url(mode, options)
        if not content_url:
            return False
        return self.start_url(content_url, content_mode=mode, options=options or {})

    def stop(self) -> bool:
        if self.sender:
            self.sender.disconnect()
            self.sender = None
        return True

    def record_heartbeat(self) -> bool:
        if not self.sender:
            return False
        self.sender.record_heartbeat()
        return True

    def set_power_state(self, power_state: str) -> None:
        if self.sender:
            self.sender.set_power_state(power_state)

    def status(self) -> Dict[str, Any]:
        target_name = self.projector_config.get("target_name")
        sender_status = self.sender.get_status() if self.sender else None
        runtime_status = "idle"
        if sender_status:
            runtime_status = sender_status.get("projection_state", "idle")

        status = {
            "scene_id": self.scene_id,
            "projector_id": self.projector_id,
            "sender_type": "hdmi",
            "target_name": target_name,
            "content_mode": self.content_mode,
            "options": self.options,
            "status": runtime_status,
        }
        if sender_status:
            status["sender_status"] = sender_status
        return status

    def content_mode_url(self, mode: str, options: Optional[Dict[str, Any]] = None) -> Optional[str]:
        options = dict(options or {})
        page_by_mode = {
            "identify": "hdmi_identify.html",
            "blank": "blank.html",
        }
        if mode == "overlay":
            overlay_options = dict(options)
            controls_hidden = overlay_options.pop("controls", "hidden") == "hidden"
            config_id = overlay_options.pop("config_id", None)
            return build_overlay_window_url(
                self.server_base_url,
                config_id=config_id,
                controls_hidden=controls_hidden,
                projector_id=self.projector_id,
                mode=mode,
                extra_params=overlay_options,
            )
        page = page_by_mode.get(mode)
        if not page:
            self.logger.error("Unsupported projector content mode: %s", mode)
            return None

        params = {"projector_id": self.projector_id, "mode": mode}
        params.update(
            {
                key: self._url_param_value(value)
                for key, value in options.items()
                if value is not None
            }
        )
        return f"{self.server_base_url}/backend-static/{page}?{urlencode(params)}"

    @staticmethod
    def _url_param_value(value: Any) -> Any:
        if isinstance(value, bool):
            return str(value).lower()
        return value
