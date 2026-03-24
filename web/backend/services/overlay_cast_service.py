import asyncio
import base64
import logging
import queue
import re
import socket
import subprocess
import sys
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import urlencode

from discovery.discovery_manager import DiscoveryManager

logger = logging.getLogger(__name__)
RELAY_IDLE_TIMEOUT_SECONDS = 15
SESSION_HISTORY_LIMIT = 12
FFMPEG_SPEED_RE = re.compile(r"speed=\s*([0-9.]+)x")
FFMPEG_FPS_RE = re.compile(r"fps=\s*([0-9.]+)")
FFMPEG_BITRATE_RE = re.compile(r"bitrate=\s*([0-9.]+)kbits/s")


class OverlayCastRelayHandler(BaseHTTPRequestHandler):
    server_version = "OverlayCastRelay/1.0"

    def log_message(self, format, *args):
        logger.debug("Overlay cast relay: " + format, *args)

    def do_GET(self):
        if self.path != "/live.ts":
            self.send_error(404)
            return

        ffmpeg_proc = getattr(self.server, "ffmpeg_proc", None)
        if ffmpeg_proc is None or ffmpeg_proc.stdout is None:
            self.send_error(503, "Relay not ready")
            return

        self.send_response(200)
        self.send_header("Content-Type", "video/mpeg")
        self.end_headers()

        session = getattr(self.server, "overlay_session", None)
        if session is not None:
            session.active_clients += 1
            session.last_client_connected_at = datetime.utcnow()
            session.last_client_activity_at = session.last_client_connected_at

        try:
            while True:
                chunk = ffmpeg_proc.stdout.read(65536)
                if not chunk:
                    break
                self.wfile.write(chunk)
                if session is not None:
                    session.last_client_activity_at = datetime.utcnow()
        except (BrokenPipeError, ConnectionResetError):
            logger.info("Overlay cast relay client disconnected during transfer")
        except Exception as exc:
            logger.warning("Overlay cast relay stream error: %s", exc)
        finally:
            if session is not None:
                session.active_clients = max(0, session.active_clients - 1)
                session.last_client_disconnected_at = datetime.utcnow()


@dataclass
class OverlayCastSession:
    session_id: str
    device_id: str
    config_id: int
    overlay_url: str
    relay_url: str
    stream_port: int
    status: str = "starting"
    archived: bool = False
    started_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    error: Optional[str] = None
    current_step: str = "queued"
    debug_log: list[str] = field(default_factory=list)
    active_clients: int = 0
    ffmpeg_speed: Optional[float] = None
    ffmpeg_fps: Optional[float] = None
    ffmpeg_bitrate_kbps: Optional[float] = None
    last_client_connected_at: Optional[datetime] = None
    last_client_disconnected_at: Optional[datetime] = None
    last_client_activity_at: Optional[datetime] = None
    discovery_session_id: Optional[str] = None
    task: Optional[asyncio.Task] = None
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    browser = None
    page = None
    ffmpeg_proc: Optional[subprocess.Popen] = None
    relay_server: Optional[ThreadingHTTPServer] = None
    relay_thread: Optional[threading.Thread] = None
    ffmpeg_log_thread: Optional[threading.Thread] = None
    frame_queue: Optional[queue.Queue] = None
    frame_writer_thread: Optional[threading.Thread] = None

    def to_dict(self) -> dict:
        return {
            "session_id": self.session_id,
            "device_id": self.device_id,
            "config_id": self.config_id,
            "overlay_url": self.overlay_url,
            "relay_url": self.relay_url,
            "stream_port": self.stream_port,
            "status": self.status,
            "archived": self.archived,
            "current_step": self.current_step,
            "debug_log": self.debug_log,
            "active_clients": self.active_clients,
            "ffmpeg_speed": self.ffmpeg_speed,
            "ffmpeg_fps": self.ffmpeg_fps,
            "ffmpeg_bitrate_kbps": self.ffmpeg_bitrate_kbps,
            "last_client_connected_at": self.last_client_connected_at.isoformat() if self.last_client_connected_at else None,
            "last_client_disconnected_at": self.last_client_disconnected_at.isoformat() if self.last_client_disconnected_at else None,
            "last_client_activity_at": self.last_client_activity_at.isoformat() if self.last_client_activity_at else None,
            "started_at": self.started_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "error": self.error,
            "discovery_session_id": self.discovery_session_id,
        }


class OverlayCastService:
    _instance = None
    _lock = threading.Lock()

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.discovery_manager = DiscoveryManager.get_instance()
        self.sessions: Dict[str, OverlayCastSession] = {}
        self.device_sessions: Dict[str, str] = {}
        self.session_history: list[dict] = []
        self._session_lock = threading.RLock()

    async def start_cast(
        self,
        device_id: str,
        config_id: int,
        overlay_base_url: str,
        controls_hidden: bool = True,
        viewport_width: int = 1920,
        viewport_height: int = 1080,
        capture_width: int = 1280,
        capture_height: int = 720,
        quality: int = 30,
        frame_rate: int = 15,
        stream_port: Optional[int] = None,
    ) -> dict:
        with self._session_lock:
            existing_session_id = self.device_sessions.get(device_id)
            if existing_session_id:
                await self._stop_session(existing_session_id)

            relay_port = stream_port or self._reserve_free_port()
            relay_url = f"http://{self._get_local_ip()}:{relay_port}/live.ts"
            overlay_url = self._build_overlay_url(overlay_base_url, config_id, controls_hidden)
            session_id = str(uuid.uuid4())
            session = OverlayCastSession(
                session_id=session_id,
                device_id=device_id,
                config_id=config_id,
                overlay_url=overlay_url,
                relay_url=relay_url,
                stream_port=relay_port,
            )
            self._log_step(session, "queued", f"Queued cast for device {device_id} using overlay config {config_id}")
            session.task = asyncio.create_task(
                self._run_session(
                    session,
                    viewport_width=viewport_width,
                    viewport_height=viewport_height,
                    capture_width=capture_width,
                    capture_height=capture_height,
                    quality=quality,
                    frame_rate=frame_rate,
                )
            )
            self.sessions[session_id] = session
            self.device_sessions[device_id] = session_id

        try:
            await asyncio.wait_for(session.ready_event.wait(), timeout=10)
        except asyncio.TimeoutError as exc:
            await self._stop_session(session.session_id)
            raise RuntimeError("Overlay cast start timed out before relay became ready") from exc

        if session.status == "error":
            message = session.error or "Overlay cast failed to start"
            await self._stop_session(session.session_id)
            raise RuntimeError(message)

        return session.to_dict()

    async def stop_cast(self, session_id: str) -> bool:
        with self._session_lock:
            return await self._stop_session(session_id)

    async def stop_all(self):
        with self._session_lock:
            for session_id in list(self.sessions.keys()):
                await self._stop_session(session_id)

    def list_sessions(self) -> list[dict]:
        active = [session.to_dict() for session in self.sessions.values()]
        return sorted(
            active + list(self.session_history),
            key=lambda session: session.get("updated_at", ""),
            reverse=True,
        )

    def get_session_for_device(self, device_id: str) -> Optional[dict]:
        session_id = self.device_sessions.get(device_id)
        if not session_id:
            return None
        session = self.sessions.get(session_id)
        return session.to_dict() if session else None

    async def _run_session(
        self,
        session: OverlayCastSession,
        viewport_width: int,
        viewport_height: int,
        capture_width: int,
        capture_height: int,
        quality: int,
        frame_rate: int,
    ):
        playwright_context = None

        try:
            try:
                from playwright.async_api import async_playwright
            except ImportError as exc:
                raise RuntimeError(
                    "Playwright is required for overlay casting. Install it in the backend environment."
                ) from exc

            session.status = "preparing"
            self._log_step(session, "preparing", "Initializing Playwright")

            playwright_context = await async_playwright().start()
            self._log_step(session, "browser_launch", "Launching headless Chromium")
            browser = await playwright_context.chromium.launch(
                headless=True,
                args=["--no-sandbox"],
            )
            self._log_step(session, "page_create", "Opening overlay page")
            page = await browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            await page.goto(session.overlay_url)
            self._log_step(session, "page_loaded", f"Overlay page loaded: {session.overlay_url}")

            ffmpeg_cmd = [
                "ffmpeg",
                "-y",
                "-f",
                "image2pipe",
                "-vcodec",
                "mjpeg",
                "-r",
                str(frame_rate),
                "-i",
                "-",
                "-c:v",
                "h264_videotoolbox",
                "-b:v",
                "2000k",
                "-pix_fmt",
                "yuv420p",
                "-color_range",
                "2",
                "-realtime",
                "1",
                "-profile:v",
                "baseline",
                "-level",
                "4.1",
                "-r",
                str(frame_rate),
                "-g",
                str(max(frame_rate * 2, 1)),
                "-f",
                "mpegts",
                "-muxrate",
                "2500k",
                "pipe:1",
            ]
            self._log_step(session, "ffmpeg_start", "Starting FFmpeg encoder")
            ffmpeg_proc = subprocess.Popen(
                ffmpeg_cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            if ffmpeg_proc.poll() is not None:
                raise RuntimeError("FFmpeg exited immediately during startup")
            ffmpeg_log_thread = threading.Thread(
                target=self._pump_ffmpeg_logs,
                args=(session, ffmpeg_proc),
                daemon=True,
            )
            ffmpeg_log_thread.start()
            frame_queue: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=max(frame_rate * 2, 4))
            frame_writer_thread = threading.Thread(
                target=self._pump_frames_to_ffmpeg,
                args=(session, ffmpeg_proc, frame_queue),
                daemon=True,
            )
            frame_writer_thread.start()

            self._log_step(session, "relay_bind", f"Starting local relay on port {session.stream_port}")
            relay_server = ThreadingHTTPServer(("0.0.0.0", session.stream_port), OverlayCastRelayHandler)
            relay_server.ffmpeg_proc = ffmpeg_proc
            relay_server.overlay_session = session
            relay_thread = threading.Thread(target=relay_server.serve_forever, daemon=True)
            relay_thread.start()
            self._log_step(session, "relay_ready", f"Relay is listening at {session.relay_url}")

            cdp = await page.context.new_cdp_session(page)

            async def on_frame(event):
                if session.stop_event.is_set():
                    return
                try:
                    self._enqueue_frame(session, base64.b64decode(event["data"]))
                    await cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
                except Exception as exc:
                    logger.debug("Overlay cast frame handling stopped: %s", exc)

            self._log_step(session, "screencast_start", "Starting Chrome DevTools screencast")
            cdp.on("Page.screencastFrame", lambda event: asyncio.create_task(on_frame(event)))
            await cdp.send(
                "Page.startScreencast",
                {
                    "format": "jpeg",
                    "quality": quality,
                    "maxWidth": capture_width,
                    "maxHeight": capture_height,
                    "everyNthFrame": 1,
                },
            )

            session.browser = browser
            session.page = page
            session.ffmpeg_proc = ffmpeg_proc
            session.relay_server = relay_server
            session.relay_thread = relay_thread
            session.ffmpeg_log_thread = ffmpeg_log_thread
            session.frame_queue = frame_queue
            session.frame_writer_thread = frame_writer_thread
            session.ready_event.set()

            self._log_step(session, "priming", "Priming pipeline before DLNA handoff")
            await asyncio.sleep(5)

            self._log_step(session, "dlna_cast", f"Sending relay URL to DLNA device {session.device_id}")
            discovery_session = await self.discovery_manager.cast_content(
                device_id=session.device_id,
                content_url=session.relay_url,
                content_type="video/mpeg",
                metadata={
                    "source": "overlay_cast",
                    "config_id": session.config_id,
                    "overlay_url": session.overlay_url,
                },
            )
            if not discovery_session:
                raise RuntimeError("DLNA cast command failed")

            session.discovery_session_id = discovery_session.id
            session.status = "running"
            self._log_step(session, "running", "DLNA cast acknowledged and session is running")
            logger.info(
                "Started overlay cast session %s for device %s using config %s",
                session.session_id,
                session.device_id,
                session.config_id,
            )

            while not session.stop_event.is_set():
                if ffmpeg_proc.poll() is not None:
                    raise RuntimeError("FFmpeg exited unexpectedly")
                if (
                    session.status == "running" and
                    session.active_clients == 0 and
                    session.last_client_disconnected_at is not None and
                    (datetime.utcnow() - session.last_client_disconnected_at).total_seconds() > RELAY_IDLE_TIMEOUT_SECONDS
                ):
                    raise RuntimeError("Relay client disconnected and did not reconnect")
                await asyncio.sleep(1)

        except asyncio.CancelledError:
            session.status = "stopping"
            self._log_step(session, "stopping", "Overlay cast was cancelled")
            session.ready_event.set()
            raise
        except Exception as exc:
            session.status = "error"
            session.error = str(exc)
            self._log_step(session, "error", f"Startup failed: {exc}")
            session.ready_event.set()
            logger.error("Overlay cast session %s failed: %s", session.session_id, exc)
        finally:
            await self._cleanup_session_resources(session)
            if playwright_context is not None:
                try:
                    await playwright_context.stop()
                except Exception:
                    pass
            if session.status not in {"error", "stopped"}:
                session.status = "stopped"
                self._log_step(session, "stopped", "Overlay cast session stopped")

    async def _stop_session(self, session_id: str) -> bool:
        session = self.sessions.get(session_id)
        if not session:
            return False

        session.stop_event.set()
        session.status = "stopping"
        self._log_step(session, "stopping", "Stopping overlay cast session")

        if session.discovery_session_id:
            try:
                await self.discovery_manager.stop_casting(session.discovery_session_id)
            except Exception as exc:
                logger.warning("Failed to stop discovery cast session %s: %s", session.discovery_session_id, exc)

        if session.task:
            session.task.cancel()
            try:
                await session.task
            except asyncio.CancelledError:
                pass
            except Exception:
                pass

        self.device_sessions.pop(session.device_id, None)
        self.sessions.pop(session_id, None)
        session.status = "stopped"
        self._log_step(session, "stopped", "Overlay cast session stopped and cleaned up")
        self._archive_session(session)
        return True

    async def _cleanup_session_resources(self, session: OverlayCastSession):
        if session.page is not None:
            try:
                await session.page.close()
            except Exception:
                pass
            session.page = None

        if session.browser is not None:
            try:
                await session.browser.close()
            except Exception:
                pass
            session.browser = None

        if session.ffmpeg_proc is not None:
            if session.frame_queue is not None:
                try:
                    session.frame_queue.put_nowait(None)
                except queue.Full:
                    try:
                        session.frame_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        session.frame_queue.put_nowait(None)
                    except queue.Full:
                        pass
            try:
                if session.ffmpeg_proc.stdin is not None:
                    session.ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                session.ffmpeg_proc.kill()
            except Exception:
                pass
            session.ffmpeg_proc = None

        if session.relay_server is not None:
            try:
                session.relay_server.shutdown()
                session.relay_server.server_close()
            except Exception:
                pass
            session.relay_server = None

        if session.relay_thread is not None:
            session.relay_thread = None
        if session.ffmpeg_log_thread is not None:
            session.ffmpeg_log_thread = None
        if session.frame_writer_thread is not None:
            session.frame_writer_thread = None
        if session.frame_queue is not None:
            session.frame_queue = None

    def _build_overlay_url(self, overlay_base_url: str, config_id: int, controls_hidden: bool) -> str:
        base = overlay_base_url.rstrip("/")
        params = {"config_id": config_id}
        if controls_hidden:
            params["controls"] = "hidden"
        return f"{base}/backend-static/overlay_window.html?{urlencode(params)}"

    def _get_local_ip(self) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            sock.connect(("10.255.255.255", 1))
            return sock.getsockname()[0]
        except Exception:
            return "127.0.0.1"
        finally:
            sock.close()

    def _reserve_free_port(self) -> int:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.bind(("0.0.0.0", 0))
        port = sock.getsockname()[1]
        sock.close()
        return port

    def _log_step(self, session: OverlayCastSession, step: str, message: str):
        session.current_step = step
        session.updated_at = datetime.utcnow()
        timestamp = session.updated_at.strftime("%H:%M:%S")
        session.debug_log.append(f"[{timestamp}] {step}: {message}")
        session.debug_log = session.debug_log[-30:]
        logger.info("Overlay cast %s %s: %s", session.session_id, step, message)

    def _enqueue_frame(self, session: OverlayCastSession, frame_data: bytes):
        if session.frame_queue is None or session.stop_event.is_set():
            return

        try:
            session.frame_queue.put_nowait(frame_data)
        except queue.Full:
            try:
                session.frame_queue.get_nowait()
            except queue.Empty:
                return
            try:
                session.frame_queue.put_nowait(frame_data)
            except queue.Full:
                logger.debug("Dropping overlay cast frame for session %s due to sustained backpressure", session.session_id)

    def _archive_session(self, session: OverlayCastSession):
        session.archived = True
        self.session_history = [entry for entry in self.session_history if entry.get("session_id") != session.session_id]
        self.session_history.insert(0, session.to_dict())
        self.session_history = self.session_history[:SESSION_HISTORY_LIMIT]

    def _pump_ffmpeg_logs(self, session: OverlayCastSession, ffmpeg_proc: subprocess.Popen):
        if ffmpeg_proc.stderr is None:
            return

        try:
            for raw_line in iter(ffmpeg_proc.stderr.readline, b""):
                if not raw_line:
                    break
                line = raw_line.decode("utf-8", errors="replace").strip()
                if not line:
                    continue
                speed_match = FFMPEG_SPEED_RE.search(line)
                if speed_match:
                    session.ffmpeg_speed = float(speed_match.group(1))
                fps_match = FFMPEG_FPS_RE.search(line)
                if fps_match:
                    session.ffmpeg_fps = float(fps_match.group(1))
                bitrate_match = FFMPEG_BITRATE_RE.search(line)
                if bitrate_match:
                    session.ffmpeg_bitrate_kbps = float(bitrate_match.group(1))
                self._log_step(session, "ffmpeg", line)
        except Exception as exc:
            logger.debug("Failed to capture FFmpeg logs for overlay cast %s: %s", session.session_id, exc)

    def _pump_frames_to_ffmpeg(
        self,
        session: OverlayCastSession,
        ffmpeg_proc: subprocess.Popen,
        frame_queue: queue.Queue,
    ):
        while not session.stop_event.is_set():
            try:
                frame = frame_queue.get(timeout=0.5)
            except queue.Empty:
                continue

            if frame is None:
                break

            try:
                if ffmpeg_proc.stdin is None:
                    break
                ffmpeg_proc.stdin.write(frame)
                ffmpeg_proc.stdin.flush()
            except Exception as exc:
                logger.warning("Overlay cast frame writer stopped for session %s: %s", session.session_id, exc)
                session.error = str(exc)
                session.stop_event.set()
                break


def get_overlay_cast_service() -> OverlayCastService:
    return OverlayCastService.get_instance()
