import time
from typing import Any, Dict, Optional


class RuntimeRegistryService:
    """
    Own live device runtime state while preserving the legacy dict-based access model.
    """

    def __init__(self):
        self._device_status: Dict[str, Dict[str, Any]] = {}
        self._last_seen: Dict[str, float] = {}
        self._device_connected_at: Dict[str, float] = {}

    @property
    def device_status(self) -> Dict[str, Dict[str, Any]]:
        return self._device_status

    @property
    def last_seen(self) -> Dict[str, float]:
        return self._last_seen

    @property
    def device_connected_at(self) -> Dict[str, float]:
        return self._device_connected_at

    def ensure_device(self, device_name: str, now: Optional[float] = None) -> Dict[str, Any]:
        now = time.time() if now is None else now
        if device_name not in self._device_status:
            self._device_status[device_name] = {
                "status": "connected",
                "last_updated": now,
                "is_playing": False,
                "last_seen_at": now,
                "last_lost_at": None,
                "reconnect_count": 0,
                "degraded_count": 0,
                "offline_count": 0,
            }
        if device_name not in self._last_seen:
            self._last_seen[device_name] = now
        return self._device_status[device_name]

    def mark_seen(self, device_name: str, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self.ensure_device(device_name, now)
        self._last_seen[device_name] = now
        self._device_status[device_name]["last_seen_at"] = now
        self._device_status[device_name]["last_updated"] = now

    def set_connected_at(self, device_name: str, now: Optional[float] = None) -> None:
        now = time.time() if now is None else now
        self._device_connected_at[device_name] = now

    def update_status(
        self,
        device_name: str,
        status: str,
        is_playing: Optional[bool] = None,
        current_video: Optional[str] = None,
        error: Optional[str] = None,
        now: Optional[float] = None,
    ) -> Dict[str, Any]:
        now = time.time() if now is None else now
        status_dict = self.ensure_device(device_name, now)

        previous_status = status_dict.get("status")
        previous_online = previous_status in {"connected", "playing"}
        next_online = status in {"connected", "playing"}

        status_dict["status"] = status
        status_dict["last_updated"] = now

        if next_online:
            status_dict["last_seen_at"] = now
            self._last_seen[device_name] = now
            if not previous_online and previous_status is not None:
                status_dict["reconnect_count"] = int(status_dict.get("reconnect_count", 0)) + 1
        elif status in {"disconnected", "offline"}:
            if previous_status not in {"disconnected", "offline"}:
                status_dict["offline_count"] = int(status_dict.get("offline_count", 0)) + 1
                status_dict["last_lost_at"] = now
        elif status in {"streaming_issue", "error"}:
            if previous_status != status:
                status_dict["degraded_count"] = int(status_dict.get("degraded_count", 0)) + 1
            if status == "error" and status_dict.get("last_lost_at") is None:
                status_dict["last_lost_at"] = now

        if is_playing is not None:
            status_dict["is_playing"] = is_playing

        if current_video is not None:
            status_dict["current_video"] = current_video

        if error is not None:
            status_dict["last_error"] = error
            status_dict["last_error_time"] = now

        return status_dict

    def update_playback_progress(self, device_name: str, position: str, duration: str, progress: int) -> Dict[str, Any]:
        status_dict = self.ensure_device(device_name)
        status_dict["playback_position"] = position
        status_dict["playback_duration"] = duration
        status_dict["playback_progress"] = progress
        status_dict["last_updated"] = time.time()
        return status_dict

    def update_playing_state(self, device_name: str, is_playing: bool, video_path: Optional[str] = None) -> Dict[str, Any]:
        status_dict = self.ensure_device(device_name)
        status_dict["is_playing"] = is_playing
        status_dict["current_video"] = video_path if video_path else status_dict.get("current_video")
        status_dict["last_updated"] = time.time()
        return status_dict

    def remove_device(self, device_name: str) -> None:
        self._device_status.pop(device_name, None)
        self._last_seen.pop(device_name, None)
        self._device_connected_at.pop(device_name, None)
