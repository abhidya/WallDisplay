import logging
import os
import re
import time
from typing import Any, Dict, Optional


logger = logging.getLogger(__name__)


class RuntimePlaybackService:
    """
    Own runtime autoplay/stream-and-play execution outside the legacy manager.
    """

    def __init__(self, runtime):
        self.runtime = runtime

    def auto_play_video(
        self,
        device: Any,
        video_path: str,
        loop: bool = True,
        config: Optional[Dict[str, Any]] = None,
    ) -> bool:
        try:
            logger.info("Auto-playing video %s on device %s", video_path, device.name)
            is_remote_url = bool(re.match(r"^https?://", video_path, re.IGNORECASE))

            try:
                runtime_result = self.runtime.play_runtime_device_video(device.name, video_path, loop)
                if runtime_result is not None:
                    logger.info(
                        "Using runtime device-service flow for stream reuse on device %s",
                        device.name,
                    )
                    return runtime_result
            except Exception as exc:
                logger.warning(
                    "Failed to use runtime device-service flow: %s, falling back to direct play",
                    exc,
                )

            if not is_remote_url and not os.path.exists(video_path):
                logger.error("Video file not found: %s", video_path)
                self.runtime.update_device_status(
                    device_name=device.name,
                    status="error",
                    error="Video file not found",
                )
                return False

            if device.is_playing:
                logger.info("Stopping current playback on %s", device.name)
                device.stop()
                time.sleep(1)

            if is_remote_url:
                success = device.play(video_path, loop)
                if not success:
                    logger.error("Failed to play remote URL on device %s", device.name)
                    self.runtime.update_device_status(
                        device_name=device.name,
                        status="error",
                        error="Failed to play video",
                    )
                    return False

                if hasattr(device, "current_video_path"):
                    device.current_video_path = video_path

                self.runtime.update_device_status(
                    device_name=device.name,
                    status="connected",
                    is_playing=True,
                    current_video=video_path,
                )
                self.runtime.start_playback_health_check(device.name, video_path)

                if config and config.get("enable_overlay_sync"):
                    sync_video_name = config.get("sync_video_name", os.path.basename(video_path))
                    self.runtime.trigger_overlay_sync(sync_video_name)

                return True

            serve_ip = self.runtime.get_serve_ip()
            file_name = os.path.basename(video_path)
            files_dict = {file_name: video_path}

            from core.twisted_streaming import TwistedStreamingServer

            streaming_server = TwistedStreamingServer.get_instance()

            try:
                urls, server = streaming_server.start_server(
                    files=files_dict,
                    serve_ip=serve_ip,
                    port=None,
                    port_range=(9000, 9100),
                )
            except Exception as exc:
                logger.error("Failed to start streaming server: %s", exc)
                self.runtime.update_device_status(
                    device_name=device.name,
                    status="error",
                    error=f"Failed to start streaming server: {str(exc)}",
                )
                return False

            device._current_streaming_server = server
            video_url = urls[file_name]
            port_match = re.search(r":(\d+)/", video_url)
            streaming_port = int(port_match.group(1)) if port_match else None
            device.update_streaming_info(video_url, streaming_port)

            if hasattr(device, "current_video_path"):
                device.current_video_path = video_path

            success = device.play(video_url, loop)
            if not success:
                logger.error("Failed to play video on device %s", device.name)
                streaming_server.stop_server()
                self.runtime.update_device_status(
                    device_name=device.name,
                    status="error",
                    error="Failed to play video",
                )
                return False

            self.runtime.update_device_status(
                device_name=device.name,
                status="connected",
                is_playing=True,
                current_video=video_path,
            )

            from core.streaming_registry import StreamingSessionRegistry

            registry = StreamingSessionRegistry.get_instance()
            session = registry.register_session(
                device_name=device.name,
                video_path=video_path,
                server_ip=serve_ip,
                server_port=streaming_port,
            )
            logger.debug("Registered streaming session %s for device %s", session.session_id, device.name)

            self.runtime.start_playback_health_check(device.name, video_path)

            if config and config.get("enable_overlay_sync"):
                sync_video_name = config.get("sync_video_name", os.path.basename(video_path))
                self.runtime.trigger_overlay_sync(sync_video_name)

            return True
        except Exception as exc:
            logger.error("Error auto-playing video: %s", exc)
            self.runtime.update_device_status(
                device_name=device.name,
                status="error",
                error=str(exc),
            )
            return False
