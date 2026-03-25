import logging
import os
import threading
import time
from typing import Any, Dict

logger = logging.getLogger(__name__)


class PlaybackMonitoringService:
    """
    Own per-device playback monitoring loops and playback history/state.
    """

    def __init__(self, manager: Any):
        self.playback_health_check_interval = getattr(manager, "playback_health_check_interval", 30)
        self.device_state_lock = getattr(manager, "device_state_lock", None)
        self.playback_intent_service = getattr(manager, "playback_intent_service", None)
        self.playback_orchestrator = getattr(manager, "playback_orchestrator", None)
        self.streaming_registry = getattr(manager, "streaming_registry", None)
        self.device_status = getattr(manager, "device_status", {})
        self.get_device = getattr(manager, "get_device", lambda _device_name: None)
        self.get_db_device_by_name = getattr(manager, "get_db_device_by_name", None)
        self._monitoring_lock = threading.Lock()
        self._playback_health_threads: Dict[str, Dict[str, Any]] = {}
        self._video_playback_history: Dict[str, Dict[str, Any]] = {}
        self._playback_stats: Dict[str, Any] = {}

    @property
    def monitoring_lock(self) -> threading.Lock:
        return self._monitoring_lock

    @property
    def playback_health_threads(self) -> Dict[str, Dict[str, Any]]:
        return self._playback_health_threads

    @property
    def video_playback_history(self) -> Dict[str, Dict[str, Any]]:
        return self._video_playback_history

    @property
    def playback_stats(self) -> Dict[str, Any]:
        return self._playback_stats

    def run_health_check_loop(self, device_name: str, video_path: str) -> None:
        logger.info("Starting playback health monitoring for %s", device_name)
        consecutive_failures = 0
        max_consecutive_failures = 3
        check_interval = self.playback_health_check_interval

        while True:
            try:
                time.sleep(check_interval)

                with self._monitoring_lock:
                    if (
                        device_name not in self._playback_health_threads
                        or not self._playback_health_threads.get(device_name, {}).get("active", False)
                    ):
                        logger.info("Stopping playback health monitoring for %s", device_name)
                        break

                device = self.get_device(device_name)
                if not device:
                    logger.warning("Device %s not found, stopping health check", device_name)
                    break

                if not device.is_playing:
                    logger.warning(
                        "Device %s is not playing but should be. Consecutive failure: %s/%s",
                        device_name,
                        consecutive_failures + 1,
                        max_consecutive_failures,
                    )
                    consecutive_failures += 1

                    if consecutive_failures >= max_consecutive_failures:
                        logger.warning(
                            "Device %s playback consistently failing, attempting recovery",
                            device_name,
                        )

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
                                if (
                                    db_device
                                    and db_device.user_control_mode == "manual"
                                    and db_device.user_control_reason == "user_stopped"
                                ):
                                    logger.info(
                                        "Device %s was manually stopped, skipping auto-recovery",
                                        device_name,
                                    )
                                    break
                            except Exception as exc:
                                logger.warning(
                                    "Could not check user control mode for %s: %s",
                                    device_name,
                                    exc,
                                )

                        with self.device_state_lock:
                            current_video = self.playback_intent_service.get_assigned_video(device_name)

                        if current_video and os.path.exists(current_video):
                            if self.playback_orchestrator.restart_assigned_video(
                                device_name,
                                device,
                                loop=True,
                            ):
                                consecutive_failures = 0
                elif consecutive_failures > 0:
                    logger.info(
                        "Device %s is now playing correctly, resetting failure counter",
                        device_name,
                    )
                    consecutive_failures = 0

                active_sessions = self.streaming_registry.get_sessions_for_device(device_name)

                if device.is_playing and not active_sessions:
                    logger.warning(
                        "Device %s is playing but has no active streaming sessions",
                        device_name,
                    )

                    with self.device_state_lock:
                        assigned_video = self.playback_intent_service.get_assigned_video(device_name)
                        if assigned_video and device.current_video != assigned_video:
                            self.playback_orchestrator.restart_assigned_video(
                                device_name,
                                device,
                                loop=True,
                            )

                streaming_issues = False
                for session in active_sessions:
                    if session.status in ["stalled", "error"]:
                        logger.warning(
                            "Streaming session %s for device %s has status %s",
                            session.session_id,
                            device_name,
                            session.status,
                        )
                        streaming_issues = True

                with self.device_state_lock:
                    if device_name in self.device_status:
                        self.device_status[device_name]["active_streaming_sessions"] = len(active_sessions)
                        self.device_status[device_name]["streaming_issues"] = streaming_issues

                        if active_sessions:
                            total_bytes = sum(session.bytes_served for session in active_sessions)
                            avg_bandwidth = (
                                sum(session.get_bandwidth() for session in active_sessions) / len(active_sessions)
                            )

                            self.device_status[device_name]["streaming_bytes"] = total_bytes
                            self.device_status[device_name]["streaming_bandwidth_bps"] = avg_bandwidth

            except Exception as exc:
                logger.error("Error in playback health check for %s: %s", device_name, exc)
                time.sleep(5)

        logger.info("Playback health monitoring stopped for %s", device_name)

        with self._monitoring_lock:
            self._playback_health_threads.pop(device_name, None)

    def start_health_check(self, device_name: str, video_path: str) -> None:
        self.stop_health_check(device_name)

        health_thread = threading.Thread(
            target=self.run_health_check_loop,
            args=[device_name, video_path],
            daemon=True,
        )

        with self._monitoring_lock:
            self._playback_health_threads[device_name] = {
                "thread": health_thread,
                "active": True,
                "video_path": video_path,
            }

        health_thread.start()
        logger.info("Started playback health check for %s", device_name)

    def stop_health_check(self, device_name: str) -> None:
        with self._monitoring_lock:
            if device_name in self._playback_health_threads:
                self._playback_health_threads[device_name]["active"] = False
                logger.info("Stopped playback health check for %s", device_name)

    def track_playback_result(self, device_name: str, video_path: str, success: bool) -> None:
        with self._monitoring_lock:
            if device_name not in self._video_playback_history:
                self._video_playback_history[device_name] = {
                    "attempts": 0,
                    "successes": 0,
                    "last_attempt": time.time(),
                    "videos": {},
                }

            history = self._video_playback_history[device_name]
            history["attempts"] += 1
            if success:
                history["successes"] += 1
            history["last_attempt"] = time.time()

            if video_path not in history["videos"]:
                history["videos"][video_path] = {
                    "attempts": 0,
                    "successes": 0,
                }

            video_stats = history["videos"][video_path]
            video_stats["attempts"] += 1
            if success:
                video_stats["successes"] += 1

    def get_device_playback_stats(self, device_name: str) -> Dict[str, Any]:
        with self._monitoring_lock:
            if device_name not in self._video_playback_history:
                return {
                    "attempts": 0,
                    "successes": 0,
                    "success_rate": 0,
                    "last_attempt": None,
                    "videos": {},
                }

            history = self._video_playback_history[device_name]
            success_rate = (history["successes"] / history["attempts"]) * 100 if history["attempts"] > 0 else 0

            return {
                "attempts": history["attempts"],
                "successes": history["successes"],
                "success_rate": success_rate,
                "last_attempt": history["last_attempt"],
                "videos": history["videos"],
            }

    def clear_device_state(self, device_name: str) -> None:
        with self._monitoring_lock:
            if device_name in self._playback_health_threads:
                self._playback_health_threads[device_name]["active"] = False
                del self._playback_health_threads[device_name]
            self._video_playback_history.pop(device_name, None)
