import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from models.device import DeviceModel
from services.overlay_cast_service import get_overlay_cast_service

logger = logging.getLogger(__name__)


class DeviceViewService:
    """
    Assemble frontend-facing device read models from persisted state and live runtime state.
    """

    def __init__(self, runtime: Any):
        self.device_status = runtime.device_status
        self.device_state_lock = runtime.device_state_lock
        self.get_device = runtime.get_device
        self.connectivity_timeout = getattr(runtime, "connectivity_timeout", 30)

    def build_device_dict(self, device: DeviceModel) -> Dict[str, Any]:
        """
        Convert a DeviceModel to a dictionary, incorporating live status from the runtime facade.
        """
        device_dict = {
            "id": device.id,
            "name": device.name,
            "type": device.type,
            "hostname": device.hostname,
            "friendly_name": device.friendly_name,
            "location": device.location,
            "manufacturer": device.manufacturer,
            "action_url": device.action_url,
            "status": device.status,
            "is_playing": device.is_playing,
            "current_video": device.current_video,
            "playback_position": device.playback_position,
            "playback_duration": device.playback_duration,
            "playback_progress": device.playback_progress,
            "playback_started_at": self.format_datetime_utc(device.playback_started_at),
            "config": device.config,
            "created_at": self.format_datetime_utc(device.created_at),
            "updated_at": self.format_datetime_utc(device.updated_at),
        }

        logger.debug(
            "_device_to_dict for device.name='%s' with manager status keys=%s",
            device.name,
            list(self.device_status.keys()),
        )

        with self.device_state_lock:
            if device.name in self.device_status:
                status_info = self.device_status[device.name]
                device_dict["status"] = status_info.get("status", device.status)
                device_dict["last_seen"] = status_info.get("last_updated")
                device_dict["manager_is_playing"] = status_info.get("is_playing", device.is_playing)
                device_dict["last_seen_at"] = status_info.get("last_seen_at")
                device_dict["last_lost_at"] = status_info.get("last_lost_at")
                device_dict["reconnect_count"] = status_info.get("reconnect_count", 0)
                device_dict["degraded_count"] = status_info.get("degraded_count", 0)
                device_dict["offline_count"] = status_info.get("offline_count", 0)

        device_dict.update(self.derive_runtime_state(device, device_dict))
        return device_dict

    def build_device_detail_dict(self, device: DeviceModel) -> Dict[str, Any]:
        """
        Build the device detail read model, including live core-device and streaming-session state.
        """
        device_dict = self.build_device_dict(device)

        core_device = self.get_device(device.name)
        if core_device:
            device_dict["is_playing"] = core_device.is_playing
            device_dict["current_video"] = core_device.current_video

        try:
            from core.streaming_registry import StreamingSessionRegistry

            registry = StreamingSessionRegistry.get_instance()
            sessions = registry.get_sessions_for_device(device.name)
            if sessions:
                device_dict["streaming_sessions"] = len(sessions)
                device_dict["streaming_session_ids"] = [session.session_id for session in sessions]

                active_sessions = [session for session in sessions if session.active]
                if active_sessions:
                    latest_session = max(active_sessions, key=lambda session: session.last_activity_time)
                    device_dict["streaming_details"] = {
                        "session_id": latest_session.session_id,
                        "video_path": latest_session.video_path,
                        "server_ip": latest_session.server_ip,
                        "server_port": latest_session.server_port,
                        "bytes_served": latest_session.bytes_served,
                        "client_ip": latest_session.client_ip,
                        "connection_count": latest_session.client_connections,
                        "error_count": latest_session.connection_errors,
                        "status": latest_session.status,
                        "bandwidth_bps": latest_session.get_bandwidth(),
                        "last_activity": latest_session.last_activity_time.isoformat(),
                    }
        except (ImportError, Exception) as exc:
            logger.warning(f"Error getting streaming session info: {exc}")

        return device_dict

    def derive_runtime_state(self, device: DeviceModel, device_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce stable, presentation-friendly availability fields from raw DB and manager state.
        This does not change persisted device status; it only normalizes what the frontend sees.
        """
        now = time.time()
        timeout = self.connectivity_timeout
        degraded_threshold = timeout
        offline_threshold = timeout * 2

        manager_status = device_dict.get("status") or device.status or "unknown"
        manager_is_playing = device_dict.get("manager_is_playing", device_dict.get("is_playing", False))
        last_seen_raw = device_dict.get("last_seen")

        last_seen_ts = None
        if isinstance(last_seen_raw, (int, float)):
            last_seen_ts = float(last_seen_raw)

        seconds_since_seen = None if last_seen_ts is None else max(0.0, now - last_seen_ts)

        if manager_status in {"playing", "connected"}:
            if seconds_since_seen is None or seconds_since_seen <= degraded_threshold:
                availability = "online"
            elif seconds_since_seen <= offline_threshold:
                availability = "degraded"
            else:
                availability = "offline"
        elif manager_status in {"streaming_issue", "error"}:
            availability = "degraded" if seconds_since_seen is None or seconds_since_seen <= offline_threshold else "offline"
        elif manager_status in {"disconnected", "offline"}:
            availability = "offline"
        else:
            availability = "unknown"

        connected_since = None
        downtime_started_at = None
        uptime_seconds = None
        downtime_seconds = None
        last_lost_at = device_dict.get("last_lost_at")

        if availability in {"online", "degraded"} and last_seen_ts is not None:
            connected_since = last_seen_ts if seconds_since_seen is None else max(
                last_seen_ts - min(seconds_since_seen, degraded_threshold), 0
            )
            uptime_seconds = max(0.0, now - connected_since)
        elif availability == "offline":
            if isinstance(last_lost_at, (int, float)):
                downtime_started_at = float(last_lost_at)
                downtime_seconds = max(0.0, now - downtime_started_at)
            elif last_seen_ts is not None:
                downtime_started_at = last_seen_ts + offline_threshold
                downtime_seconds = max(0.0, now - downtime_started_at)

        overlay_cast = self.get_overlay_cast_state(device)

        return {
            "availability": availability,
            "derived_status": availability,
            "manager_status": manager_status,
            "manager_is_playing": manager_is_playing,
            "seconds_since_seen": seconds_since_seen,
            "connected_since": connected_since,
            "uptime_seconds": uptime_seconds,
            "downtime_started_at": downtime_started_at,
            "downtime_seconds": downtime_seconds,
            "last_seen_at": device_dict.get("last_seen_at"),
            "last_lost_at": last_lost_at,
            "reconnect_count": int(device_dict.get("reconnect_count", 0) or 0),
            "degraded_count": int(device_dict.get("degraded_count", 0) or 0),
            "offline_count": int(device_dict.get("offline_count", 0) or 0),
            **overlay_cast,
        }

    def get_overlay_cast_state(self, device: DeviceModel) -> Dict[str, Any]:
        active_session = None
        cast_service = get_overlay_cast_service()
        for session in cast_service.list_sessions():
            if session.get("archived"):
                continue
            if self.overlay_session_matches_device(session, device):
                active_session = session
                break

        if not active_session:
            return {
                "active_overlay_cast": False,
                "overlay_cast_status": None,
                "overlay_cast_started_at": None,
                "overlay_cast_uptime_seconds": None,
                "overlay_cast_current_step": None,
                "overlay_cast_ffmpeg_speed": None,
                "overlay_cast_ffmpeg_fps": None,
                "overlay_cast_ffmpeg_bitrate_kbps": None,
                "overlay_cast_active_clients": 0,
                "overlay_cast_session_id": None,
            }

        started_at_raw = active_session.get("started_at")
        started_at = None
        overlay_cast_uptime_seconds = None
        if started_at_raw:
            if isinstance(started_at_raw, str):
                try:
                    started_at = datetime.fromisoformat(started_at_raw)
                except ValueError:
                    started_at = None
            elif isinstance(started_at_raw, datetime):
                started_at = started_at_raw
            if started_at is not None:
                now_utc = datetime.now(timezone.utc).replace(tzinfo=None)
                overlay_cast_uptime_seconds = max(
                    0.0,
                    (now_utc - started_at.replace(tzinfo=None)).total_seconds(),
                )

        return {
            "active_overlay_cast": True,
            "overlay_cast_status": active_session.get("status"),
            "overlay_cast_started_at": started_at_raw,
            "overlay_cast_uptime_seconds": overlay_cast_uptime_seconds,
            "overlay_cast_current_step": active_session.get("current_step"),
            "overlay_cast_ffmpeg_speed": active_session.get("ffmpeg_speed"),
            "overlay_cast_ffmpeg_fps": active_session.get("ffmpeg_fps"),
            "overlay_cast_ffmpeg_bitrate_kbps": active_session.get("ffmpeg_bitrate_kbps"),
            "overlay_cast_active_clients": active_session.get("active_clients", 0),
            "overlay_cast_session_id": active_session.get("session_id"),
        }

    def overlay_session_matches_device(self, session: Dict[str, Any], device: DeviceModel) -> bool:
        device_id = session.get("device_id")
        if not device_id or device.type != "dlna" or not device.hostname:
            return False

        expected_prefix = f"dlna_{device.hostname}_"
        if device_id.startswith(expected_prefix):
            return True

        if device.action_url:
            parsed = urlparse(device.action_url)
            if parsed.hostname == device.hostname and parsed.port is not None:
                return device_id == f"dlna_{parsed.hostname}_{parsed.port}"

        return False

    def format_datetime_utc(self, dt: Optional[datetime]) -> Optional[str]:
        if not dt:
            return None

        if dt.tzinfo is None:
            return dt.isoformat() + "Z"

        utc_dt = dt.astimezone(timezone.utc)
        return utc_dt.isoformat().replace("+00:00", "Z")
