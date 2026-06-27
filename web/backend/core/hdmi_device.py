import json
import logging
import os
import urllib.parse
import urllib.request
from typing import Any, Dict, Optional

from .device import Device

logger = logging.getLogger(__name__)


class HDMIDevice(Device):
    """
    Runtime adapter for a local HDMI projector managed by RendererService.

    HDMI is not a network player. Playback means asking the local renderer API to
    open a fullscreen browser window on the configured display target.
    """

    def __init__(self, device_info: Dict[str, Any]):
        super().__init__(device_info)
        self.type = "hdmi"
        self.projector_id = (
            device_info.get("renderer_projector_id")
            or device_info.get("projector_id")
            or device_info.get("device_name")
        )
        self.target_name = device_info.get("target_name") or device_info.get("hostname")

    def play(self, video_url: str, loop: bool = False) -> bool:
        if not self.projector_id:
            logger.error("HDMI device %s has no renderer projector id", self.name)
            return False

        page_url = self._video_player_url(video_url)
        payload = {
            "content_url": page_url,
            "content_mode": "video",
            "options": {
                "source": "device-playback",
                "loop": bool(loop),
                "video_url": video_url,
            },
        }
        if not self._post_json(f"/api/renderer/projectors/{self.projector_id}/url", payload):
            return False

        self.update_status("playing")
        self.update_playing(True)
        self.update_video(video_url)
        return True

    def stop(self) -> bool:
        if not self.projector_id:
            return False
        if not self._post_json("/api/renderer/stop", {"projector": self.projector_id}):
            return False
        self.update_status("connected")
        self.update_playing(False)
        self.update_video(None)
        return True

    def pause(self) -> bool:
        logger.info("Pause is not supported for HDMI projector %s", self.name)
        return False

    def seek(self, position: str) -> bool:
        logger.info("Seek is not supported for HDMI projector %s", self.name)
        return False

    def _video_player_url(self, video_url: str) -> str:
        base_url = self._server_base_url()
        query = urllib.parse.urlencode(
            {
                "projector_id": self.projector_id,
                "src": video_url,
            }
        )
        return f"{base_url}/backend-static/hdmi_video_player.html?{query}"

    def _post_json(self, path: str, payload: Dict[str, Any]) -> bool:
        url = f"{self._server_base_url()}{path}"
        try:
            request = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(request, timeout=15) as response:
                if response.status >= 400:
                    logger.error("HDMI renderer request failed: %s %s", response.status, url)
                    return False
            return True
        except Exception as exc:
            logger.error("HDMI renderer request failed for %s: %s", url, exc)
            return False

    @staticmethod
    def _server_base_url() -> str:
        base_url: Optional[str] = (
            os.environ.get("NANODLNA_SERVER_BASE_URL")
            or os.environ.get("WALLDISPLAY_SERVER_BASE_URL")
        )
        if not base_url:
            port = os.environ.get("NANODLNA_BACKEND_PORT", "8088")
            base_url = f"http://127.0.0.1:{port}"
        return base_url.rstrip("/")
