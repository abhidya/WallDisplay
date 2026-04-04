import asyncio
import base64
import html
import ipaddress
import os
import logging
import queue
import re
import socket
import subprocess
import sys
import threading
import time
import shutil
import tempfile
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Dict, Optional
from urllib.parse import urlencode

import aiohttp

from discovery.base import CastingSession
from discovery.discovery_manager import DiscoveryManager
from discovery.network import get_local_ipv4_addresses

logger = logging.getLogger(__name__)
RELAY_IDLE_TIMEOUT_SECONDS = 15
SESSION_HISTORY_LIMIT = 12
DEFAULT_PRIMING_SECONDS = 6
DEFAULT_CAST_CAPTURE_WIDTH = 960
DEFAULT_CAST_CAPTURE_HEIGHT = 540
DEFAULT_CAST_QUALITY = 28
DEFAULT_CAST_FRAME_RATE = 10
FFMPEG_SPEED_RE = re.compile(r"speed=\s*([0-9.]+)x")
FFMPEG_FPS_RE = re.compile(r"fps=\s*([0-9.]+)")
FFMPEG_BITRATE_RE = re.compile(r"bitrate=\s*([0-9.]+)kbits/s")
FFMPEG_PROGRESS_KEYS = {"speed", "fps", "bitrate"}
OVERLAY_STREAM_PATH = "/live.mp4"
OVERLAY_STREAM_CONTENT_TYPE = "video/mp4"
OVERLAY_DLNA_PROTOCOL_INFO = "http-get:*:video/mp4:*"


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class FanoutRelayState:
    def __init__(self):
        self._clients: dict[str, queue.Queue] = {}
        self._lock = threading.Lock()
        self.closed = False

    def register_client(self) -> tuple[str, queue.Queue]:
        client_id = str(uuid.uuid4())
        client_queue: queue.Queue = queue.Queue(maxsize=128)
        with self._lock:
            self._clients[client_id] = client_queue
        return client_id, client_queue

    def unregister_client(self, client_id: str):
        with self._lock:
            self._clients.pop(client_id, None)

    def publish(self, chunk: bytes):
        if not chunk:
            return
        with self._lock:
            for client_id, client_queue in self._clients.items():
                try:
                    client_queue.put_nowait(chunk)
                except queue.Full:
                    try:
                        client_queue.get_nowait()
                    except queue.Empty:
                        pass
                    try:
                        client_queue.put_nowait(chunk)
                    except queue.Full:
                        logger.debug("Overlay cast relay client %s is still backpressured; dropping chunk", client_id)

    def close(self):
        with self._lock:
            self.closed = True
            clients = list(self._clients.values())
            self._clients.clear()
        for client_queue in clients:
            try:
                client_queue.put_nowait(None)
            except queue.Full:
                pass

    @property
    def active_client_count(self) -> int:
        with self._lock:
            return len(self._clients)


class OverlayCastRelayHandler(BaseHTTPRequestHandler):
    server_version = "OverlayCastRelay/1.0"
    protocol_version = "HTTP/1.1"

    def log_message(self, format, *args):
        logger.debug("Overlay cast relay: " + format, *args)

    def do_GET(self):
        if self.path != OVERLAY_STREAM_PATH:
            self.send_error(404)
            return

        relay_state: Optional[FanoutRelayState] = getattr(self.server, "relay_state", None)
        if relay_state is None:
            self.send_error(503, "Relay not ready")
            return

        self.send_response(200)
        self.send_header("Content-Type", OVERLAY_STREAM_CONTENT_TYPE)
        self.send_header("Connection", "keep-alive")
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()

        session = getattr(self.server, "overlay_session", None)
        client_id, client_queue = relay_state.register_client()
        if session is not None:
            session.active_clients = relay_state.active_client_count
            session.last_client_connected_at = datetime.utcnow()
            session.last_client_activity_at = session.last_client_connected_at

        try:
            while True:
                try:
                    chunk = client_queue.get(timeout=1.0)
                except queue.Empty:
                    if relay_state.closed:
                        break
                    continue
                if chunk is None:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
                if session is not None:
                    session.last_client_activity_at = datetime.utcnow()
        except (BrokenPipeError, ConnectionResetError):
            logger.info("Overlay cast relay client disconnected during transfer")
        except Exception as exc:
            logger.warning("Overlay cast relay stream error: %s", exc)
        finally:
            relay_state.unregister_client(client_id)
            if session is not None:
                session.active_clients = relay_state.active_client_count
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
    encoder: Optional[str] = None
    task: Optional[asyncio.Task] = None
    ready_event: asyncio.Event = field(default_factory=asyncio.Event)
    stop_event: asyncio.Event = field(default_factory=asyncio.Event)
    browser = None
    page = None
    ffmpeg_proc: Optional[subprocess.Popen] = None
    relay_state: Optional[FanoutRelayState] = None
    relay_server: Optional[ThreadingHTTPServer] = None
    relay_thread: Optional[threading.Thread] = None
    ffmpeg_log_thread: Optional[threading.Thread] = None
    ffmpeg_stdout_thread: Optional[threading.Thread] = None
    frame_decode_thread: Optional[threading.Thread] = None
    frame_writer_thread: Optional[threading.Thread] = None
    latest_frame: Optional[bytes] = None
    pending_frame_b64: Optional[str] = None
    frame_decode_lock: threading.Lock = field(default_factory=threading.Lock)
    frame_decode_event: threading.Event = field(default_factory=threading.Event)
    frame_interval_seconds: float = 1 / 20
    relay_reconnect_attempts: int = 0

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
            "encoder": self.encoder,
            "relay_reconnect_attempts": self.relay_reconnect_attempts,
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

    async def export_mp4(
        self,
        config_id: int,
        overlay_base_url: str,
        controls_hidden: bool = True,
        hide_widgets: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        capture_width: int = 1280,
        capture_height: int = 720,
        quality: int = 80,
        frame_rate: int = 24,
        duration_seconds: int = 30,
        bitrate_kbps: int = 2500,
    ) -> dict:
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            raise RuntimeError(
                "Playwright is required for overlay export. Install it in the backend environment."
            ) from exc

        duration_seconds = max(1, min(int(duration_seconds or 30), 900))
        bitrate_kbps = max(250, int(bitrate_kbps or 2500))
        frame_interval = 1 / max(frame_rate, 1)
        export_dir = tempfile.mkdtemp(prefix="overlay_export_")
        export_path = os.path.join(export_dir, f"overlay_config_{config_id}_{int(time.time())}.mp4")
        session = OverlayCastSession(
            session_id=str(uuid.uuid4()),
            device_id="export",
            config_id=config_id,
            overlay_url=self._build_overlay_url(overlay_base_url, config_id, controls_hidden, hide_widgets),
            relay_url="",
            stream_port=0,
            frame_interval_seconds=frame_interval,
        )
        playwright_context = None
        browser = None
        page = None
        ffmpeg_proc = None

        try:
            playwright_context = await async_playwright().start()
            launch_kwargs = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--enable-gpu",
                    "--ignore-gpu-blocklist",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            }
            if sys.platform == "darwin":
                launch_kwargs["args"].append("--use-angle=metal")
            elif sys.platform.startswith("linux"):
                launch_kwargs["args"].extend(["--use-angle=egl", "--use-gl=egl"])
            chrome_path = shutil.which("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") or shutil.which("google-chrome")
            if chrome_path:
                launch_kwargs["channel"] = "chrome"

            browser = await playwright_context.chromium.launch(**launch_kwargs)
            page = await browser.new_page(viewport={"width": viewport_width, "height": viewport_height})
            await page.goto(session.overlay_url)

            ffmpeg_proc = subprocess.Popen(
                self._build_export_ffmpeg_command(frame_rate, bitrate_kbps, export_path),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
            )
            if ffmpeg_proc.poll() is not None:
                raise RuntimeError("FFmpeg export process exited immediately during startup")

            frame_decode_thread = threading.Thread(
                target=self._pump_latest_frame_decode,
                args=(session,),
                daemon=True,
            )
            frame_decode_thread.start()

            frame_writer_thread = threading.Thread(
                target=self._pump_latest_frame_to_ffmpeg,
                args=(session, ffmpeg_proc),
                daemon=True,
            )
            frame_writer_thread.start()

            cdp = await page.context.new_cdp_session(page)

            async def on_frame(event):
                if session.stop_event.is_set():
                    return
                try:
                    with session.frame_decode_lock:
                        session.pending_frame_b64 = event["data"]
                    session.frame_decode_event.set()
                    await cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})
                except Exception:
                    return

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

            await asyncio.sleep(duration_seconds)
            session.stop_event.set()
            session.frame_decode_event.set()
            if ffmpeg_proc.stdin is not None:
                ffmpeg_proc.stdin.close()
            ffmpeg_proc.wait(timeout=30)
            if ffmpeg_proc.returncode not in (0, None):
                stderr_output = ""
                if ffmpeg_proc.stderr is not None:
                    stderr_output = ffmpeg_proc.stderr.read().decode("utf-8", errors="replace").strip()
                raise RuntimeError(stderr_output or f"FFmpeg export failed with code {ffmpeg_proc.returncode}")

            def iter_file_chunks(path: str):
                try:
                    with open(path, "rb") as handle:
                        while True:
                            chunk = handle.read(1024 * 1024)
                            if not chunk:
                                break
                            yield chunk
                finally:
                    try:
                        os.remove(path)
                    except OSError:
                        pass
                    try:
                        os.rmdir(os.path.dirname(path))
                    except OSError:
                        pass

            return {
                "file_name": os.path.basename(export_path),
                "file_iterator": iter_file_chunks(export_path),
            }
        finally:
            session.stop_event.set()
            session.frame_decode_event.set()
            if ffmpeg_proc is not None and ffmpeg_proc.poll() is None:
                try:
                    if ffmpeg_proc.stdin is not None:
                        ffmpeg_proc.stdin.close()
                except Exception:
                    pass
                try:
                    ffmpeg_proc.kill()
                except Exception:
                    pass
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass
            if browser is not None:
                try:
                    await browser.close()
                except Exception:
                    pass
            if playwright_context is not None:
                try:
                    await playwright_context.stop()
                except Exception:
                    pass

    async def start_cast(
        self,
        device_id: str,
        config_id: int,
        overlay_base_url: str,
        controls_hidden: bool = True,
        viewport_width: int = 1280,
        viewport_height: int = 720,
        capture_width: int = DEFAULT_CAST_CAPTURE_WIDTH,
        capture_height: int = DEFAULT_CAST_CAPTURE_HEIGHT,
        quality: int = DEFAULT_CAST_QUALITY,
        frame_rate: int = DEFAULT_CAST_FRAME_RATE,
        stream_port: Optional[int] = None,
    ) -> dict:
        with self._session_lock:
            existing_session_id = self.device_sessions.get(device_id)
            if existing_session_id:
                await self._stop_session(existing_session_id)

            relay_port = stream_port or self._reserve_free_port()
            relay_url = f"http://{self._get_local_ip(device_id)}:{relay_port}{OVERLAY_STREAM_PATH}"
            overlay_url = self._build_overlay_url(
                overlay_base_url,
                config_id,
                controls_hidden,
                capture_mode="dlna",
            )
            session_id = str(uuid.uuid4())
            session = OverlayCastSession(
                session_id=session_id,
                device_id=device_id,
                config_id=config_id,
                overlay_url=overlay_url,
                relay_url=relay_url,
                stream_port=relay_port,
                frame_interval_seconds=1 / max(frame_rate, 1),
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
            await asyncio.wait_for(session.ready_event.wait(), timeout=12)
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
            launch_kwargs = {
                "headless": True,
                "args": [
                    "--no-sandbox",
                    "--enable-gpu",
                    "--ignore-gpu-blocklist",
                    "--disable-background-timer-throttling",
                    "--disable-backgrounding-occluded-windows",
                    "--disable-renderer-backgrounding",
                ],
            }
            if sys.platform == "darwin":
                launch_kwargs["args"].append("--use-angle=metal")
            elif sys.platform.startswith("linux"):
                launch_kwargs["args"].extend(["--use-angle=egl", "--use-gl=egl"])
            chrome_path = shutil.which("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") or shutil.which("google-chrome")
            if chrome_path:
                launch_kwargs["channel"] = "chrome"
            browser = await playwright_context.chromium.launch(**launch_kwargs)
            self._log_step(session, "page_create", "Opening overlay page")
            page = await browser.new_page(
                viewport={"width": viewport_width, "height": viewport_height}
            )
            await page.goto(session.overlay_url)
            self._log_step(session, "page_loaded", f"Overlay page loaded: {session.overlay_url}")

            encoder, ffmpeg_cmd = self._build_ffmpeg_command(
                frame_rate=frame_rate,
                capture_width=capture_width,
                capture_height=capture_height,
            )
            session.encoder = encoder
            self._log_step(session, "ffmpeg_start", f"Starting FFmpeg encoder with {encoder}")
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

            relay_state = FanoutRelayState()
            ffmpeg_stdout_thread = threading.Thread(
                target=self._pump_ffmpeg_stdout,
                args=(session, ffmpeg_proc, relay_state),
                daemon=True,
            )
            ffmpeg_stdout_thread.start()

            frame_decode_thread = threading.Thread(
                target=self._pump_latest_frame_decode,
                args=(session,),
                daemon=True,
            )
            frame_decode_thread.start()

            frame_writer_thread = threading.Thread(
                target=self._pump_latest_frame_to_ffmpeg,
                args=(session, ffmpeg_proc),
                daemon=True,
            )
            frame_writer_thread.start()

            self._log_step(session, "relay_bind", f"Starting local relay on port {session.stream_port}")
            relay_server = ReusableThreadingHTTPServer(("0.0.0.0", session.stream_port), OverlayCastRelayHandler)
            relay_server.relay_state = relay_state
            relay_server.overlay_session = session
            relay_thread = threading.Thread(target=relay_server.serve_forever, daemon=True)
            relay_thread.start()
            self._log_step(session, "relay_ready", f"Relay is listening at {session.relay_url}")

            cdp = await page.context.new_cdp_session(page)

            async def on_frame(event):
                if session.stop_event.is_set():
                    return
                try:
                    with session.frame_decode_lock:
                        session.pending_frame_b64 = event["data"]
                    session.frame_decode_event.set()
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
            session.relay_state = relay_state
            session.relay_server = relay_server
            session.relay_thread = relay_thread
            session.ffmpeg_log_thread = ffmpeg_log_thread
            session.ffmpeg_stdout_thread = ffmpeg_stdout_thread
            session.frame_decode_thread = frame_decode_thread
            session.frame_writer_thread = frame_writer_thread
            session.ready_event.set()

            self._log_step(session, "priming", "Priming pipeline before DLNA handoff")
            await asyncio.sleep(DEFAULT_PRIMING_SECONDS)

            self._log_step(session, "dlna_cast", f"Sending relay URL to DLNA device {session.device_id}")
            await self._direct_dlna_handshake(session)
            session.discovery_session_id = None
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
                    if session.relay_reconnect_attempts < 1:
                        session.relay_reconnect_attempts += 1
                        self._log_step(
                            session,
                            "relay_reconnect",
                            "Relay client disconnected; retrying DLNA handoff without metadata",
                        )
                        await self._direct_dlna_handshake(session, include_metadata=False)
                        session.last_client_disconnected_at = datetime.utcnow()
                    else:
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
        else:
            try:
                await self._direct_dlna_stop(session)
            except Exception as exc:
                logger.warning("Failed to stop direct overlay cast for %s: %s", session.device_id, exc)

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
            try:
                if session.ffmpeg_proc.stdin is not None:
                    session.ffmpeg_proc.stdin.close()
            except Exception:
                pass
            try:
                if session.ffmpeg_proc.stdout is not None:
                    session.ffmpeg_proc.stdout.close()
            except Exception:
                pass
            try:
                session.ffmpeg_proc.kill()
            except Exception:
                pass
            session.ffmpeg_proc = None

        if session.relay_state is not None:
            session.relay_state.close()
            session.relay_state = None

        if session.relay_server is not None:
            try:
                session.relay_server.shutdown()
                session.relay_server.server_close()
            except Exception:
                pass
            session.relay_server = None

        session.relay_thread = None
        session.ffmpeg_log_thread = None
        session.ffmpeg_stdout_thread = None
        session.frame_decode_thread = None
        session.frame_writer_thread = None
        session.latest_frame = None
        session.pending_frame_b64 = None
        session.frame_decode_event.set()

    def _build_overlay_url(
        self,
        overlay_base_url: str,
        config_id: int,
        controls_hidden: bool,
        hide_widgets: bool = False,
        capture_mode: Optional[str] = None,
    ) -> str:
        base = overlay_base_url.rstrip("/")
        params = {"config_id": config_id}
        if controls_hidden:
            params["controls"] = "hidden"
        if hide_widgets:
            params["widgets"] = "hidden"
        if capture_mode:
            params["capture"] = capture_mode
        return f"{base}/backend-static/overlay_window.html?{urlencode(params)}"

    def _get_local_ip(self, device_id: Optional[str] = None) -> str:
        for env_name in ("STREAMING_SERVE_IP", "NANODLNA_DISCOVERY_INTERFACE_IP", "SERVE_IP"):
            env_ip = os.environ.get(env_name)
            if env_ip and not env_ip.startswith("127.") and env_ip != "localhost":
                return env_ip

        local_addresses = sorted(get_local_ipv4_addresses())
        device = self.discovery_manager.get_device_by_id(device_id) if device_id else None
        device_ip = getattr(device, "hostname", None)
        if device_ip:
            try:
                device_network = ipaddress.ip_network(f"{device_ip}/24", strict=False)
                for address in local_addresses:
                    if ipaddress.ip_address(address) in device_network:
                        return address
            except ValueError:
                pass

        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            target_ip = device_ip or "8.8.8.8"
            sock.connect((target_ip, 80))
            candidate = sock.getsockname()[0]
            if candidate and not candidate.startswith("127."):
                return candidate
        except Exception:
            pass
        finally:
            sock.close()

        if local_addresses:
            return local_addresses[0]
        return "127.0.0.1"

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
                key, sep, value = line.partition("=")
                if sep and key in FFMPEG_PROGRESS_KEYS:
                    if key == "speed":
                        try:
                            session.ffmpeg_speed = float(value.replace("x", "").strip())
                        except ValueError:
                            pass
                    elif key == "fps":
                        try:
                            session.ffmpeg_fps = float(value.strip())
                        except ValueError:
                            pass
                    elif key == "bitrate":
                        try:
                            session.ffmpeg_bitrate_kbps = float(value.replace("kbits/s", "").strip())
                        except ValueError:
                            pass
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

    def _pump_latest_frame_to_ffmpeg(self, session: OverlayCastSession, ffmpeg_proc: subprocess.Popen):
        while not session.stop_event.is_set():
            try:
                if ffmpeg_proc.stdin is None:
                    break
                if session.latest_frame:
                    ffmpeg_proc.stdin.write(session.latest_frame)
                    ffmpeg_proc.stdin.flush()
            except Exception as exc:
                if session.stop_event.is_set() or ffmpeg_proc.poll() is not None:
                    break
                logger.warning("Overlay cast frame writer stopped for session %s: %s", session.session_id, exc)
                session.error = str(exc)
                session.stop_event.set()
                break
            time.sleep(session.frame_interval_seconds)

    def _pump_latest_frame_decode(self, session: OverlayCastSession):
        while not session.stop_event.is_set():
            session.frame_decode_event.wait(timeout=0.25)
            if session.stop_event.is_set():
                break
            session.frame_decode_event.clear()
            pending_frame_b64 = None
            with session.frame_decode_lock:
                pending_frame_b64 = session.pending_frame_b64
                session.pending_frame_b64 = None
            if not pending_frame_b64:
                continue
            try:
                session.latest_frame = base64.b64decode(pending_frame_b64)
            except Exception as exc:
                logger.warning("Overlay cast frame decode stopped for session %s: %s", session.session_id, exc)
                session.error = str(exc)
                session.stop_event.set()
                break

    def _pump_ffmpeg_stdout(
        self,
        session: OverlayCastSession,
        ffmpeg_proc: subprocess.Popen,
        relay_state: FanoutRelayState,
    ):
        if ffmpeg_proc.stdout is None:
            relay_state.close()
            return

        try:
            while not session.stop_event.is_set():
                chunk = ffmpeg_proc.stdout.read1(32768)
                if not chunk:
                    break
                relay_state.publish(chunk)
        except Exception as exc:
            logger.warning("Overlay cast relay pump stopped for session %s: %s", session.session_id, exc)
        finally:
            relay_state.close()

    def _build_ffmpeg_command(self, frame_rate: int, capture_width: int, capture_height: int) -> tuple[str, list[str]]:
        bitrate_kbps = self._select_cast_bitrate_kbps(frame_rate, capture_width, capture_height)
        encoder = "h264_videotoolbox" if sys.platform == "darwin" else "libx264"
        if encoder == "h264_videotoolbox":
            encoder_options = [
                "-realtime",
                "1",
                "-prio_speed",
                "1",
                "-allow_sw",
                "1",
                "-profile:v",
                "baseline",
            ]
        else:
            encoder_options = [
                "-preset",
                "ultrafast",
                "-tune",
                "zerolatency",
                "-threads",
                "0",
                "-profile:v",
                "baseline",
            ]
        ffmpeg_cmd = [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-nostats",
            "-progress",
            "pipe:2",
            "-f",
            "mjpeg",
            "-framerate",
            str(frame_rate),
            "-i",
            "-",
            "-c:v",
            encoder,
            *encoder_options,
            "-b:v",
            f"{bitrate_kbps}k",
            "-maxrate",
            f"{bitrate_kbps}k",
            "-bufsize",
            f"{bitrate_kbps * 2}k",
            "-g",
            str(frame_rate),
            "-keyint_min",
            str(frame_rate),
            "-bf",
            "0",
            "-r",
            str(frame_rate),
            "-pix_fmt",
            "yuv420p",
            "-movflags",
            "+frag_keyframe+empty_moov+default_base_moof",
            "-frag_duration",
            "500000",
            "-f",
            "mp4",
            "pipe:1",
        ]
        return encoder, ffmpeg_cmd

    def _select_cast_bitrate_kbps(self, frame_rate: int, capture_width: int, capture_height: int) -> int:
        scaled_pixels = max(1, int(frame_rate)) * max(1, int(capture_width)) * max(1, int(capture_height))
        if scaled_pixels <= 640 * 360 * 8:
            return 900
        if scaled_pixels <= 960 * 540 * 12:
            return 1500
        return 2200

    def _build_export_ffmpeg_command(self, frame_rate: int, bitrate_kbps: int, output_path: str) -> list[str]:
        return [
            "ffmpeg",
            "-y",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "mjpeg",
            "-framerate",
            str(frame_rate),
            "-i",
            "-",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-profile:v",
            "high",
            "-pix_fmt",
            "yuv420p",
            "-b:v",
            f"{bitrate_kbps}k",
            "-maxrate",
            f"{bitrate_kbps}k",
            "-bufsize",
            f"{bitrate_kbps * 2}k",
            "-movflags",
            "+faststart",
            "-r",
            str(frame_rate),
            output_path,
        ]

    async def _direct_dlna_handshake(self, session: OverlayCastSession, include_metadata: bool = True) -> CastingSession:
        device = self.discovery_manager.get_device_by_id(session.device_id)
        if not device or not device.action_url:
            raise RuntimeError("DLNA device action URL not available")

        stream_url = session.relay_url
        meta = (
            '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/" '
            'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
            '<item id="0" parentID="-1" restricted="1"><dc:title>WallMapper</dc:title>'
            '<upnp:class>object.item.videoItem</upnp:class>'
            f'<res protocolInfo="{OVERLAY_DLNA_PROTOCOL_INFO}">{stream_url}</res>'
            "</item></DIDL-Lite>"
        )
        escaped_meta = html.escape(meta)

        set_uri_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:SetAVTransportURI xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>0</InstanceID>"
            f"<CurrentURI>{stream_url}</CurrentURI>"
            f"<CurrentURIMetaData>{escaped_meta if include_metadata else ''}</CurrentURIMetaData>"
            "</u:SetAVTransportURI></s:Body></s:Envelope>"
        )
        play_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:Play xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>0</InstanceID><Speed>1</Speed>"
            "</u:Play></s:Body></s:Envelope>"
        )

        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                device.action_url,
                data=set_uri_body,
                headers={
                    "Content-Type": "text/xml",
                    "SOAPACTION": '"urn:schemas-upnp-org:service:AVTransport:1#SetAVTransportURI"',
                },
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"SetAVTransportURI failed with {response.status}")

            await asyncio.sleep(3)

            async with http_session.post(
                device.action_url,
                data=play_body,
                headers={
                    "Content-Type": "text/xml",
                    "SOAPACTION": '"urn:schemas-upnp-org:service:AVTransport:1#Play"',
                },
            ) as response:
                if response.status != 200:
                    raise RuntimeError(f"Play failed with {response.status}")

        return CastingSession(
            id=str(uuid.uuid4()),
            device=device,
            content_url=stream_url,
            content_type=OVERLAY_STREAM_CONTENT_TYPE,
            metadata={
                "source": "overlay_cast",
                "config_id": session.config_id,
                "overlay_url": session.overlay_url,
                "relay_mode": "direct_dlna_handshake",
            },
        )

    async def _direct_dlna_stop(self, session: OverlayCastSession):
        device = self.discovery_manager.get_device_by_id(session.device_id)
        if not device or not device.action_url:
            return

        stop_body = (
            '<?xml version="1.0" encoding="utf-8"?>'
            '<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/">'
            '<s:Body><u:Stop xmlns:u="urn:schemas-upnp-org:service:AVTransport:1">'
            "<InstanceID>0</InstanceID>"
            "</u:Stop></s:Body></s:Envelope>"
        )
        async with aiohttp.ClientSession() as http_session:
            async with http_session.post(
                device.action_url,
                data=stop_body,
                headers={
                    "Content-Type": "text/xml",
                    "SOAPACTION": '"urn:schemas-upnp-org:service:AVTransport:1#Stop"',
                },
            ):
                return


def get_overlay_cast_service() -> OverlayCastService:
    return OverlayCastService.get_instance()
