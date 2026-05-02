import asyncio
import logging
import os
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from web.backend.services.overlay_cast_service import get_overlay_cast_service

logger = logging.getLogger(__name__)


def _noop(*_args, **_kwargs):
    return None


def _runtime_airplay_fallback(device_name: str, config: Any) -> None:
    try:
        from services.app_runtime import get_app_runtime

        get_app_runtime().process_airplay_casting(device_name, config)
    except Exception:
        _noop(device_name, config)


class PlaybackOrchestrator:
    """
    Decide what playback action should happen for a discovered device.

    During the first extraction phase this service delegates actual execution back to
    DeviceManager methods so runtime behavior remains stable while orchestration logic
    is moved out of the discovery loop.
    """

    def __init__(self, manager: Any):
        self.config_service = getattr(manager, "config_service", None)
        self.assignment_lock = getattr(manager, "assignment_lock", threading.Lock())
        self.device_state_lock = getattr(manager, "device_state_lock", threading.RLock())
        self.playback_intent_service = getattr(manager, "playback_intent_service", None)
        self.playback_monitoring_service = getattr(manager, "playback_monitoring_service", None)
        self.max_retry_attempts = getattr(manager, "max_retry_attempts", 3)
        self.retry_delay_base = getattr(manager, "retry_delay_base", 5)
        self.get_device = getattr(manager, "get_device", lambda _device_name: None)
        self.apply_airplay_casting = (
            getattr(manager, "process_airplay_casting", None)
            or getattr(manager, "_process_airplay_casting", None)
            or _runtime_airplay_fallback
        )
        self.auto_play_video = getattr(manager, "auto_play_video", lambda *_args, **_kwargs: False)
        self.resolve_discovery_device_id = getattr(manager, "_resolve_discovery_device_id", lambda *_args: None)
        self.update_device_status = getattr(manager, "update_device_status", _noop)
        self.get_db_device_by_name = getattr(manager, "get_db_device_by_name", None)

    def process_discovered_device(self, device_name: str, is_new_device: bool, is_changed_device: bool) -> None:
        device = self.get_device(device_name)
        if not device:
            logger.warning("Device %s not found, cannot process video assignment", device_name)
            return

        get_db_device_by_name = self.get_db_device_by_name
        if get_db_device_by_name is None:
            try:
                from services.app_runtime import get_app_runtime

                get_db_device_by_name = get_app_runtime().get_db_device_by_name
            except Exception:
                get_db_device_by_name = None

        if get_db_device_by_name:
            try:
                db_device = get_db_device_by_name(device_name)
                if db_device and db_device.user_control_mode != "auto":
                    logger.debug(
                        "Skipping %s - under user control mode: %s (reason: %s)",
                        device_name,
                        db_device.user_control_mode,
                        db_device.user_control_reason,
                    )
                    return
                if db_device and self.process_overlay_cast(device_name, db_device):
                    return
            except Exception as exc:
                logger.warning("Could not check user control mode for %s: %s", device_name, exc)

        scheduled_video = None
        if self.playback_intent_service is not None:
            scheduled_video = self.playback_intent_service.get_due_scheduled_video(
                device_name,
                datetime.now(timezone.utc),
            )
        if scheduled_video:
            logger.info("Found scheduled video assignment for %s: %s", device_name, scheduled_video)
            self.apply_video_assignment(device_name, scheduled_video, priority=100)
            return

        config = self.config_service.get_device_config(device_name) if self.config_service else None
        if not config:
            logger.debug("No configuration found for %s, skipping video assignment", device_name)
            return

        if config.get("airplay_mode"):
            logger.debug("Device %s is configured for airplay mode", device_name)
            self.apply_airplay_casting(device_name, config)
            return

        video_path = config.get("video_file")
        if not video_path or not os.path.exists(video_path):
            logger.error("Video file %s not found or not specified in config", video_path)
            return

        with self.device_state_lock:
            current_video = self.playback_intent_service.get_assigned_video(device_name)

        should_assign = (
            not current_video
            or current_video != video_path
            or is_new_device
            or is_changed_device
            or (device.current_video != video_path and not device.is_playing)
        )

        if should_assign:
            logger.info("Assigning video %s to device %s", video_path, device_name)
            priority = config.get("priority", 50)
            self.apply_video_assignment(device_name, video_path, priority=priority)
        else:
            logger.debug("No need to reassign video for device %s", device_name)

    def apply_video_assignment(
        self,
        device_name: str,
        video_path: str,
        priority: int = 50,
        schedule_time: Optional[datetime] = None,
    ) -> bool:
        device = self.get_device(device_name)
        if not device:
            logger.error("Device %s not found, cannot assign video", device_name)
            return False

        if not os.path.exists(video_path):
            logger.error("Video file %s does not exist", video_path)
            return False

        if schedule_time is not None:
            with self.assignment_lock:
                self.playback_intent_service.schedule_assignment(
                    device_name=device_name,
                    video_path=video_path,
                    priority=priority,
                    schedule_time=schedule_time,
                )
            logger.info("Scheduled video %s for device %s at %s", video_path, device_name, schedule_time)
            return True

        should_override = False
        current_priority = 0
        with self.assignment_lock:
            current_priority = self.playback_intent_service.get_priority(device_name, 0)
            if priority >= current_priority:
                should_override = True
                self.playback_intent_service.set_priority(device_name, priority)

        if not should_override:
            logger.debug(
                "Not overriding current video assignment for %s due to priority: %s < %s",
                device_name,
                priority,
                current_priority,
            )
            return False

        with self.device_state_lock:
            current_video = self.playback_intent_service.get_assigned_video(device_name)
            if current_video == video_path and device.is_playing:
                logger.debug("Device %s is already playing %s", device_name, video_path)
                return True

            if current_video and current_video != video_path and device.is_playing:
                logger.info("Device %s is playing %s, stopping first", device_name, current_video)
                device.stop()
                time.sleep(1)

            self.playback_intent_service.set_assigned_video(device_name, video_path)

        with self.assignment_lock:
            self.playback_intent_service.reset_retries(device_name)

        config = self.config_service.get_device_config(device_name) if self.config_service else {}
        loop_enabled = config.get("loop", True) if config else True

        logger.info("Auto-playing %s on %s with loop=%s", video_path, device_name, loop_enabled)
        result = self.auto_play_video(device, video_path, loop=loop_enabled, config=config)

        if self.playback_monitoring_service is not None:
            if result:
                self.playback_monitoring_service.start_health_check(device_name, video_path)
            self.playback_monitoring_service.track_playback_result(device_name, video_path, result)

        if not result:
            self.schedule_retry(device_name, video_path, priority)

        return result

    def schedule_retry(self, device_name: str, video_path: str, priority: int) -> None:
        with self.assignment_lock:
            retry_count = self.playback_intent_service.get_retry_count(device_name, 0)

            if retry_count >= self.max_retry_attempts:
                logger.warning(
                    "Max retry attempts (%s) reached for %s, giving up",
                    self.max_retry_attempts,
                    device_name,
                )
                self.playback_intent_service.reset_retries(device_name)
                return

            retry_count = self.playback_intent_service.increment_retries(device_name)
            delay = self.retry_delay_base * (2 ** (retry_count - 1))
            logger.info(
                "Scheduling retry %s/%s for %s in %ss",
                retry_count,
                self.max_retry_attempts,
                device_name,
                delay,
            )

        retry_timer = threading.Timer(
            delay,
            self.apply_video_assignment,
            args=[device_name, video_path, priority],
        )
        retry_timer.daemon = True
        retry_timer.start()

    def process_overlay_cast(self, device_name: str, db_device: Any) -> bool:
        config = db_device.config or {}
        if not config.get("auto_overlay_cast_enabled"):
            return False

        overlay_config_id = config.get("auto_overlay_config_id")
        if not overlay_config_id:
            logger.warning(
                "Device %s has auto overlay cast enabled without auto_overlay_config_id",
                device_name,
            )
            return False

        discovery_device_id = self.resolve_discovery_device_id(device_name, db_device.hostname)
        if not discovery_device_id:
            logger.info(
                "Device %s has overlay auto-cast configured but is not available in discovery v2 yet",
                device_name,
            )
            return False

        cast_service = get_overlay_cast_service()
        existing_session = cast_service.get_session_for_device(discovery_device_id)
        if (
            existing_session
            and existing_session.get("config_id") == overlay_config_id
            and existing_session.get("status") in {"starting", "preparing", "running"}
        ):
            logger.debug(
                "Overlay auto-cast already active for %s with config %s",
                device_name,
                overlay_config_id,
            )
            return True

        logger.info("Ensuring overlay config %s is casting to %s", overlay_config_id, device_name)
        try:
            asyncio.run(
                cast_service.start_cast(
                    device_id=discovery_device_id,
                    config_id=int(overlay_config_id),
                    overlay_base_url="http://localhost:8000",
                    controls_hidden=True,
                )
            )
            logger.info(
                "Started overlay auto-cast for %s using config %s",
                device_name,
                overlay_config_id,
            )
            return True
        except Exception as exc:
            logger.error("Failed to start overlay auto-cast for %s: %s", device_name, exc)
            return True

    def restart_assigned_video(
        self,
        device_name: str,
        device: Any,
        *,
        stop_first: bool = False,
        stop_delay_seconds: float = 0.0,
        loop: bool = True,
    ) -> bool:
        video_path = self.playback_intent_service.get_assigned_video(device_name)
        if not video_path:
            logger.warning("No assigned video found for %s during recovery", device_name)
            return False

        if not os.path.exists(video_path):
            logger.error("Video file no longer exists: %s", video_path)
            self.update_device_status(
                device_name=device_name,
                status="error",
                is_playing=False,
                error="Video file no longer exists",
            )
            return False

        logger.info("Attempting to restart video %s on device %s", video_path, device_name)
        if stop_first:
            device.stop()
            if stop_delay_seconds > 0:
                time.sleep(stop_delay_seconds)

        success = self.auto_play_video(device, video_path, loop=loop)
        if success:
            self.update_device_status(
                device_name=device_name,
                status="connected",
                is_playing=True,
                current_video=video_path,
            )
        else:
            self.update_device_status(
                device_name=device_name,
                status="error",
                is_playing=False,
                error="Failed to recover from streaming issue",
            )

        return success

    def handle_stalled_streaming_session(self, session: Any, device: Any) -> None:
        device_name = session.device_name
        self.update_device_status(
            device_name=device_name,
            status="streaming_issue",
            error="Streaming session stalled",
        )
        logger.warning("Streaming session for %s is stalled, attempting recovery", device_name)
        self.restart_assigned_video(
            device_name=device_name,
            device=device,
            stop_first=True,
            stop_delay_seconds=2.0,
            loop=True,
        )
