import logging
import os
import re
import traceback
from typing import Callable

from web.backend.models.device import DeviceModel

logger = logging.getLogger(__name__)


class DevicePlaybackService:
    """
    Own manual playback control flows that were previously implemented inline in DeviceService.
    """

    def __init__(
        self,
        *,
        db,
        runtime,
        runtime_sync_service,
        get_device_instance: Callable[[int], object],
        update_device_status: Callable[[str, str, bool], bool],
    ):
        self.db = db
        self.runtime = runtime
        self.runtime_sync_service = runtime_sync_service
        self.get_device_instance = get_device_instance
        self.update_device_status = update_device_status

    def play_video(self, device_id: int, video_path: str, loop: bool = False) -> bool:
        try:
            started_new_stream = False
            created_streaming_port = None
            created_session_id = None
            created_streaming_server = None

            def _cleanup_failed_playback_attempt() -> None:
                nonlocal created_session_id, created_streaming_port, created_streaming_server
                try:
                    from core.streaming_registry import StreamingSessionRegistry

                    registry = StreamingSessionRegistry.get_instance()
                    if created_session_id:
                        registry.unregister_session(created_session_id)
                except Exception as cleanup_exc:
                    logger.warning(f"Failed to clean up streaming session after play failure: {cleanup_exc}")

                if started_new_stream and created_streaming_server is not None and created_streaming_port is not None:
                    try:
                        created_streaming_server.stop_server(port=created_streaming_port)
                    except Exception as cleanup_exc:
                        logger.warning(f"Failed to stop streaming server on port {created_streaming_port}: {cleanup_exc}")

            device = self.get_device_instance(device_id)
            if not device:
                logger.error(f"Device with ID {device_id} not found")
                return False
            if not os.path.isabs(video_path):
                video_path = os.path.abspath(video_path)
            if not os.path.exists(video_path):
                logger.error(f"Video file {video_path} does not exist")
                return False

            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            video_url = None

            if db_device and db_device.streaming_url and db_device.current_video == video_path:
                import requests

                try:
                    response = requests.head(db_device.streaming_url, timeout=1)
                    if response.status_code < 400:
                        logger.info(f"Reusing existing stream for {video_path} on port {db_device.streaming_port}")
                        video_url = db_device.streaming_url

                        from core.streaming_registry import StreamingSessionRegistry

                        registry = StreamingSessionRegistry.get_instance()
                        existing_sessions = registry.get_sessions_for_device(device.name)
                        session_exists = any(s.server_port == db_device.streaming_port for s in existing_sessions)

                        if not session_exists:
                            session = registry.register_session(
                                device_name=device.name,
                                video_path=video_path,
                                server_ip=db_device.streaming_url.split(":")[1].strip("//"),
                                server_port=db_device.streaming_port,
                            )
                            logger.info(f"Re-registered streaming session {session.session_id} for existing stream")
                    else:
                        logger.warning(
                            f"Existing stream at {db_device.streaming_url} returned {response.status_code}, creating new stream"
                        )
                        raise Exception("Stream not accessible")
                except Exception as exc:
                    logger.warning(f"Existing stream at {db_device.streaming_url} is not accessible: {exc}")
                    db_device.streaming_url = None
                    db_device.streaming_port = None
                    self.db.commit()
                    video_url = None

            if not video_url:
                from core.twisted_streaming import TwistedStreamingServer
                from core.streaming_registry import StreamingSessionRegistry

                streaming_server = TwistedStreamingServer.get_instance()
                file_name = os.path.basename(video_path)
                files_dict = {file_name: video_path}
                serve_ip = self.runtime.get_serve_ip() if hasattr(self.runtime, "get_serve_ip") else "127.0.0.1"

                try:
                    urls, server = streaming_server.start_server(files=files_dict, serve_ip=serve_ip, port=9000)
                    video_url = urls[file_name]
                    port_match = re.search(r":(\d+)/", video_url)
                    streaming_port = int(port_match.group(1)) if port_match else None
                    started_new_stream = True
                    created_streaming_port = streaming_port
                    created_streaming_server = streaming_server

                    if db_device:
                        db_device.streaming_url = video_url
                        db_device.streaming_port = streaming_port
                        db_device.current_video = video_path
                        self.db.commit()

                        registry = StreamingSessionRegistry.get_instance()
                        existing_sessions = registry.get_sessions_for_device(device.name)
                        for existing_session in existing_sessions:
                            logger.info(
                                f"Cleaning up existing session {existing_session.session_id} before playing new video"
                            )
                            registry.unregister_session(existing_session.session_id)

                        session = registry.register_session(
                            device_name=device.name,
                            video_path=video_path,
                            server_ip=serve_ip,
                            server_port=streaming_port,
                        )
                        created_session_id = session.session_id
                        logger.info(f"Registered streaming session {session.session_id} for device {device.name}")
                except RuntimeError as exc:
                    if "No available port" in str(exc):
                        logger.error(f"Port exhaustion: {exc}")
                        streaming_server.cleanup_old_servers(keep_last=3)
                        urls, server = streaming_server.start_server(files=files_dict, serve_ip=serve_ip, port=9000)
                        video_url = urls[file_name]
                    else:
                        raise

            if not video_url:
                logger.error(f"No video URL available for device {device_id}")
                return False

            logger.info(f"Playing video {video_url} on device {device_id} (loop={loop})")
            if hasattr(device, "current_video_path"):
                device.current_video_path = video_path
            success = device.play(video_url, loop)

            if not success:
                logger.error(f"Failed to play video {video_url} on device {device_id}")
                _cleanup_failed_playback_attempt()
                if db_device and started_new_stream:
                    db_device.streaming_url = None
                    db_device.streaming_port = None
                    self.db.commit()
                return False

            db_device.is_playing = False
            self.db.commit()

            try:
                import subprocess

                result = subprocess.run(
                    ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", video_path],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    duration_seconds = int(float(result.stdout.strip()))
                    hours = duration_seconds // 3600
                    minutes = (duration_seconds % 3600) // 60
                    seconds = duration_seconds % 60
                    duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                    db_device.current_video = video_path
                    db_device.playback_duration = duration_str
                    self.db.commit()
                    logger.info(f"Set video duration: {duration_str}")
            except Exception as exc:
                logger.warning(f"Could not get video duration: {exc}")

            db_device.user_control_mode = "manual"
            db_device.user_control_reason = "user_play"
            self.db.commit()

            self.update_device_status(device.name, "connected", is_playing=True)
            logger.info(f"Video {video_url} is now playing on device {device_id}")
            return True
        except Exception as exc:
            logger.error(f"Error playing video on device {device_id}: {exc}")
            logger.error(traceback.format_exc())
            return False

    def stop_video(self, device_id: int) -> bool:
        try:
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False

            core_device = self.runtime_sync_service.get_core_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                return False

            logger.info(f"Stopping playback on device {db_device.name}")
            success = core_device.stop()

            if success:
                db_device.streaming_url = None
                db_device.streaming_port = None
                db_device.current_video = None
                db_device.user_control_mode = "manual"
                db_device.user_control_reason = "user_stopped"
                self.db.commit()

                streaming_service = getattr(self.runtime, "streaming_service", None)
                if streaming_service:
                    logger.info(f"Stopping streaming servers for device {db_device.name}")
                    streaming_service.stop_all_servers()

                streaming_registry = getattr(self.runtime, "streaming_registry", None)
                if streaming_registry:
                    sessions = streaming_registry.get_sessions_for_device(db_device.name)
                    for session in sessions:
                        session_id = getattr(session, "session_id", session)
                        logger.info(f"Unregistering streaming session {session_id} for device {db_device.name}")
                        streaming_registry.unregister_session(session_id)

                logger.info(f"Cleaning up device state for {db_device.name}")
                self.runtime.cleanup_device_state(db_device.name)

            if success:
                self.update_device_status(db_device.name, "connected", is_playing=False)
                logger.info(f"Successfully stopped playback on device {db_device.name}")
            else:
                logger.error(f"Failed to stop playback on device {db_device.name}")

            return success
        except Exception as exc:
            logger.error(f"Error stopping playback on device {device_id}: {exc}")
            return False

    def pause_video(self, device_id: int) -> bool:
        try:
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False

            core_device = self.runtime_sync_service.get_core_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                return False

            logger.info(f"Pausing playback on device {db_device.name}")
            success = core_device.pause()

            if success:
                self.update_device_status(db_device.name, "connected", is_playing=False)
                logger.info(f"Successfully paused playback on device {db_device.name}")
            else:
                logger.error(f"Failed to pause playback on device {db_device.name}")

            return success
        except Exception as exc:
            logger.error(f"Error pausing playback on device {device_id}: {exc}")
            return False

    def seek_video(self, device_id: int, position: str) -> bool:
        try:
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False

            core_device = self.runtime_sync_service.get_core_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                core_device = self.runtime_sync_service.get_or_register_core_device(db_device)
                if not core_device:
                    logger.error(f"Failed to register device {db_device.name}")
                    return False
                logger.info(f"Registered device {db_device.name} from database")

            logger.info(f"Seeking to position {position} on device {db_device.name}")
            success = core_device.seek(position)

            if success:
                logger.info(f"Successfully seeked to position {position} on device {db_device.name}")
            else:
                logger.error(f"Failed to seek to position {position} on device {db_device.name}")

            return success
        except Exception as exc:
            logger.error(f"Error seeking on device {device_id}: {exc}")
            return False

    def update_playback_progress(
        self,
        device_id: int,
        position: str,
        duration: str,
        progress: int,
    ) -> bool:
        try:
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False

            if not position or not isinstance(position, str):
                logger.error(f"Invalid position format for {db_device.name}: {position}")
                position = "00:00:00"

            if not duration or not isinstance(duration, str):
                logger.error(f"Invalid duration format for {db_device.name}: {duration}")
                duration = "00:00:00"

            if not isinstance(progress, int) or progress < 0 or progress > 100:
                logger.error(f"Invalid progress value for {db_device.name}: {progress}")
                progress = 0

            db_device.playback_position = position
            db_device.playback_duration = duration
            db_device.playback_progress = progress
            self.db.commit()

            if hasattr(self.runtime, "update_runtime_playback_progress"):
                self.runtime.update_runtime_playback_progress(
                    db_device.name,
                    position,
                    duration,
                    progress,
                )

            core_device = self.runtime_sync_service.get_core_device(db_device.name)
            if core_device:
                if hasattr(core_device, "current_position"):
                    core_device.current_position = position
                if hasattr(core_device, "duration_formatted"):
                    core_device.duration_formatted = duration
                if hasattr(core_device, "playback_progress"):
                    core_device.playback_progress = progress

            logger.info(
                "Updated playback progress for %s: %s/%s (%s%%)",
                db_device.name,
                position,
                duration,
                progress,
            )
            return True
        except Exception as exc:
            logger.error(f"Error updating playback progress for device {device_id}: {exc}")
            logger.error(traceback.format_exc())
            return False
