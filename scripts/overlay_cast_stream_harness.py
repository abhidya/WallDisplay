#!/usr/bin/env python3
"""Benchmark harness for bursty overlay capture and steady MPEG-TS output.

Two independent modes:
- overlay_capture_benchmark: Chromium/ synthetic sparse source -> scheduler -> FFmpeg
- relay_broadcast_benchmark: synthetic FFmpeg stdout -> relay -> 2 clients
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import json
import math
import os
import queue
import socket
import statistics
import subprocess
import sys
import threading
import time
from collections import deque
from contextlib import suppress
from dataclasses import asdict, dataclass, field, replace
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Optional

import aiohttp

try:
    from PIL import Image, ImageDraw
except ImportError:  # pragma: no cover
    Image = None
    ImageDraw = None


DEFAULT_OVERLAY_URL = (
    "http://mannys-mac-mini.local:3000/backend-static/overlay_window.html?config_id=2&controls=hidden"
)
FFMPEG_PROGRESS_KEYS = {
    "speed",
    "fps",
    "bitrate",
    "drop_frames",
    "dup_frames",
    "out_time_ms",
}
IDLE_BUCKETS_MS = [100, 250, 500, 1000, 2000, 5000]
WEBRTC_SCENARIOS = ["synthetic_canvas", "overlay_canvas", "synthetic_composited"]

SYNTHETIC_CANVAS_HTML = """
<!DOCTYPE html>
<html>
<body style="margin:0;background:#111;overflow:hidden">
<canvas id="mapping-canvas" width="1280" height="720" style="width:100vw;height:100vh;display:block"></canvas>
<script>
const canvas = document.getElementById('mapping-canvas');
const ctx = canvas.getContext('2d');
let tick = 0;
function render() {
  tick += 1;
  const t = tick / 60;
  ctx.fillStyle = '#111418';
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#3ec1ff';
  ctx.beginPath();
  ctx.arc(
    canvas.width * (0.5 + 0.32 * Math.sin(t)),
    canvas.height * (0.5 + 0.25 * Math.cos(t * 1.4)),
    80,
    0,
    Math.PI * 2
  );
  ctx.fill();
  ctx.fillStyle = '#ffffff';
  ctx.font = '32px sans-serif';
  ctx.fillText('synthetic_canvas', 40, 54);
  ctx.fillText(`tick=${tick}`, 40, 100);
  requestAnimationFrame(render);
}
render();
</script>
</body>
</html>
"""

SYNTHETIC_COMPOSITED_HTML = """
<!DOCTYPE html>
<html>
<body style="margin:0;background:#000;overflow:hidden">
<canvas id="mapping-canvas" width="1280" height="720" style="width:100vw;height:100vh;display:block"></canvas>
<script>
const canvas = document.getElementById('mapping-canvas');
const ctx = canvas.getContext('2d');
let tick = 0;
function render() {
  tick += 1;
  const t = tick / 60;
  const gradient = ctx.createLinearGradient(0, 0, canvas.width, canvas.height);
  gradient.addColorStop(0, '#08111f');
  gradient.addColorStop(1, '#1b3852');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < 24; i++) {
    const phase = t + i * 0.2;
    ctx.fillStyle = `hsla(${(tick + i * 20) % 360}, 80%, 60%, 0.18)`;
    ctx.beginPath();
    ctx.arc(
      canvas.width * (0.5 + 0.4 * Math.sin(phase * 0.6)),
      canvas.height * (0.5 + 0.3 * Math.cos(phase)),
      40 + (i % 5) * 8,
      0,
      Math.PI * 2
    );
    ctx.fill();
  }
  ctx.fillStyle = 'rgba(20, 20, 20, 0.85)';
  ctx.fillRect(40, 40, 360, 140);
  ctx.fillRect(860, 60, 320, 180);
  ctx.fillRect(70, 520, 480, 140);
  ctx.fillStyle = '#fff';
  ctx.font = '36px sans-serif';
  ctx.fillText('09:41 PM', 70, 105);
  ctx.font = '28px sans-serif';
  ctx.fillText('Synthetic composited scene', 70, 150);
  ctx.fillText('Queue @ Carl & Stanyan: 4m', 900, 125);
  ctx.fillText('Temp 61F', 900, 170);
  ctx.fillText('Now playing: neural_noise', 100, 600);
  requestAnimationFrame(render);
}
render();
</script>
</body>
</html>
"""


@dataclass(frozen=True)
class StreamProfile:
    name: str
    width: int
    height: int
    fps: int
    jpeg_quality: int
    bitrate_k: int


PROFILES = {
    "tiny": StreamProfile("tiny", 640, 360, 6, 20, 600),
    "low": StreamProfile("low", 854, 480, 8, 24, 900),
    "medium": StreamProfile("medium", 960, 540, 10, 30, 1500),
    "high": StreamProfile("high", 1280, 720, 15, 34, 2200),
}


@dataclass(frozen=True)
class ServiceConfigPreset:
    name: str
    viewport_width: int
    viewport_height: int
    capture_width: int
    capture_height: int
    frame_rate: int
    quality: int
    every_nth_frame: int
    relay_mode: str
    chromium_args: list[str]
    include_default_chromium_args: bool
    vt_preset: str
    bitrate_k: int
    ffmpeg_input_mode: str
    stdin_flush_mode: str
    muxrate_policy: str


SERVICE_CONFIG_PRESETS = {
    "legacy": ServiceConfigPreset(
        name="legacy",
        viewport_width=1280,
        viewport_height=720,
        capture_width=1280,
        capture_height=720,
        frame_rate=20,
        quality=30,
        every_nth_frame=5,
        relay_mode="shared-read",
        chromium_args=["--no-sandbox"],
        include_default_chromium_args=False,
        vt_preset="legacy",
        bitrate_k=2500,
        ffmpeg_input_mode="image2pipe",
        stdin_flush_mode="every",
        muxrate_policy="fixed_4000k",
    ),
    "current": ServiceConfigPreset(
        name="current",
        viewport_width=1280,
        viewport_height=720,
        capture_width=854,
        capture_height=480,
        frame_rate=12,
        quality=50,
        every_nth_frame=1,
        relay_mode="fanout",
        chromium_args=[
            "--no-sandbox",
            "--use-angle=metal",
            "--enable-gpu-rasterization",
            "--enable-zero-copy",
        ],
        include_default_chromium_args=False,
        vt_preset="current",
        bitrate_k=2000,
        ffmpeg_input_mode="mjpeg",
        stdin_flush_mode="every",
        muxrate_policy="fixed_4000k",
    ),
}


@dataclass
class ClientStats:
    name: str
    bytes_in: int = 0
    chunks: int = 0
    reconnects: int = 0
    read_timeouts: int = 0
    errors: list[str] = field(default_factory=list)


@dataclass
class FrameSnapshot:
    data: bytes
    frame_id: int
    captured_at: float


@dataclass
class FrameStore:
    latest: Optional[FrameSnapshot] = None
    previous: Optional[FrameSnapshot] = None
    lock: threading.Lock = field(default_factory=threading.Lock)
    event: threading.Event = field(default_factory=threading.Event)

    def push(self, frame: FrameSnapshot) -> None:
        with self.lock:
            self.previous = self.latest
            self.latest = frame
            self.event.set()

    def snapshot(self) -> tuple[Optional[FrameSnapshot], Optional[FrameSnapshot]]:
        with self.lock:
            return self.latest, self.previous


@dataclass
class Metrics:
    source_frame_count: int = 0
    submit_frame_count: int = 0
    source_idle_repeats: int = 0
    duplicate_skip_count: int = 0
    burst_smoothed_submits: int = 0
    interpolated_submits: int = 0
    adaptive_rate_changes: int = 0
    relay_clients: int = 0
    relay_peak_clients: int = 0
    relay_bytes_out: int = 0
    relay_drop_events: int = 0
    relay_drop_bytes: int = 0
    ffmpeg_speed: Optional[float] = None
    ffmpeg_fps: Optional[float] = None
    ffmpeg_bitrate_kbps: Optional[float] = None
    ffmpeg_dup_frames: int = 0
    ffmpeg_drop_frames: int = 0
    last_progress_at: float = 0.0
    source_arrivals: list[float] = field(default_factory=list)
    source_intervals_ms: list[float] = field(default_factory=list)
    submit_arrivals: list[float] = field(default_factory=list)
    submit_intervals_ms: list[float] = field(default_factory=list)
    source_idle_gaps_ms: list[float] = field(default_factory=list)
    stdin_block_samples_ms: list[float] = field(default_factory=list)
    ffmpeg_speed_samples: list[float] = field(default_factory=list)
    ffmpeg_fps_samples: list[float] = field(default_factory=list)
    scheduler_rate_samples: list[float] = field(default_factory=list)
    ffmpeg_progress_times: list[float] = field(default_factory=list)
    decode_samples_ms: list[float] = field(default_factory=list)

    def record_source_arrival(self, ts: float) -> None:
        self.source_frame_count += 1
        if self.source_arrivals:
            delta_ms = (ts - self.source_arrivals[-1]) * 1000.0
            self.source_intervals_ms.append(delta_ms)
            self.source_idle_gaps_ms.append(delta_ms)
        self.source_arrivals.append(ts)

    def record_submit(self, ts: float, block_ms: float, scheduler_rate_fps: float) -> None:
        self.submit_frame_count += 1
        if self.submit_arrivals:
            self.submit_intervals_ms.append((ts - self.submit_arrivals[-1]) * 1000.0)
        self.submit_arrivals.append(ts)
        self.stdin_block_samples_ms.append(block_ms)
        self.scheduler_rate_samples.append(scheduler_rate_fps)

    @staticmethod
    def _avg(values: list[float]) -> float:
        return float(statistics.mean(values)) if values else 0.0

    @staticmethod
    def _stddev(values: list[float]) -> float:
        return float(statistics.pstdev(values)) if len(values) > 1 else 0.0

    @staticmethod
    def _max(values: list[float]) -> float:
        return float(max(values)) if values else 0.0

    def source_fps(self, seconds: float) -> float:
        return self.source_frame_count / max(seconds, 0.001)

    def submit_fps(self, seconds: float) -> float:
        return self.submit_frame_count / max(seconds, 0.001)

    def idle_gap_histogram(self, gaps_ms: Optional[list[float]] = None) -> dict[str, int]:
        hist: dict[str, int] = {}
        for bucket in IDLE_BUCKETS_MS:
            hist[f"<= {bucket}ms"] = 0
        hist[f"> {IDLE_BUCKETS_MS[-1]}ms"] = 0
        for gap in (gaps_ms or self.source_idle_gaps_ms):
            placed = False
            for bucket in IDLE_BUCKETS_MS:
                if gap <= bucket:
                    hist[f"<= {bucket}ms"] += 1
                    placed = True
                    break
            if not placed:
                hist[f"> {IDLE_BUCKETS_MS[-1]}ms"] += 1
        return hist

    def stability_score(self, target_fps: float, effective_gaps_ms: Optional[list[float]] = None) -> float:
        speed_mean = self._avg(self.ffmpeg_speed_samples)
        speed_dev = 0.0 if speed_mean <= 0 else abs(speed_mean - 1.0)
        ffmpeg_fps_mean = self._avg(self.ffmpeg_fps_samples)
        fps_target_dev = abs(ffmpeg_fps_mean - target_fps) / max(target_fps, 1.0)
        fps_variance = self._stddev(self.ffmpeg_fps_samples) / max(target_fps, 1.0)
        gaps = effective_gaps_ms or self.source_idle_gaps_ms
        idle_penalty = sum(1 for gap in gaps if gap > 500) / max(len(gaps), 1)
        stdin_penalty = self._avg(self.stdin_block_samples_ms)
        raw = 100.0
        raw -= min(55.0, speed_dev * 12.0)
        raw -= min(20.0, fps_target_dev * 40.0)
        raw -= min(10.0, fps_variance * 30.0)
        raw -= min(10.0, idle_penalty * 35.0)
        raw -= min(5.0, stdin_penalty / 2.0)
        return round(max(0.0, min(100.0, raw)), 2)


def now() -> float:
    return time.monotonic()


def local_ip() -> str:
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("10.255.255.255", 1))
        return sock.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        sock.close()


def reserve_free_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("0.0.0.0", 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def safe_float(value: str) -> Optional[float]:
    try:
        return float(value)
    except Exception:
        return None


def resolve_encoder(encoder_name: str) -> str:
    if encoder_name != "auto":
        return encoder_name
    return "h264_videotoolbox" if sys.platform == "darwin" else "libx264"


def chromium_args_for_mode(gpu_mode: str, extra_args: list[str], include_default_args: bool = True) -> list[str]:
    args = []
    if include_default_args:
        args = [
            "--no-sandbox",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
        ]
    if gpu_mode == "disable-gpu":
        args += ["--disable-gpu", "--disable-gpu-compositing"]
    elif gpu_mode == "swiftshader":
        args += ["--disable-gpu", "--use-angle=swiftshader", "--enable-unsafe-swiftshader"]
    elif gpu_mode == "webgpu":
        args += ["--enable-unsafe-webgpu"]
    args.extend(extra_args)
    return args


def effective_profile(args: argparse.Namespace) -> StreamProfile:
    profile = PROFILES[args.profile]
    width = args.viewport_width or profile.width
    height = args.viewport_height or profile.height
    fps = args.stream_fps or profile.fps
    quality = args.screencast_quality or profile.jpeg_quality
    bitrate_k = args.video_bitrate_k or profile.bitrate_k
    return replace(
        profile,
        width=width,
        height=height,
        fps=int(fps),
        jpeg_quality=int(quality),
        bitrate_k=int(bitrate_k),
    )


def capture_dimensions(args: argparse.Namespace, profile: StreamProfile) -> tuple[int, int]:
    return (
        int(args.capture_width or profile.width),
        int(args.capture_height or profile.height),
    )


def build_ffmpeg_output_args(profile: StreamProfile, args: argparse.Namespace, write_to_stdout: bool) -> list[str]:
    ffmpeg_mode = args.ffmpeg_mode
    muxrate_policy = args.muxrate_policy
    if muxrate_policy == "fixed_4000k":
        muxrate_k = "4000k"
    elif muxrate_policy == "bitrate":
        muxrate_k = f"{profile.bitrate_k}k"
    elif muxrate_policy == "bitrate_x1_5":
        muxrate_k = f"{int(profile.bitrate_k * 1.5)}k"
    elif muxrate_policy == "none":
        muxrate_k = None
    else:
        muxrate_k = f"{max(4000, profile.bitrate_k * 3)}k" if ffmpeg_mode == "service_low_latency" else (
            "4000k" if ffmpeg_mode == "service" else f"{max(4000, profile.bitrate_k * 3)}k"
        )
    output_target = "pipe:1" if write_to_stdout else "-"
    output_args = [
        "-pix_fmt", "yuv420p",
        "-f", "mpegts",
        "-pcr_period", "20",
    ]
    if muxrate_k is not None:
        output_args[2:2] = ["-muxrate", muxrate_k]
    if ffmpeg_mode == "service":
        gop = int(args_ns_gop(profile, args))
        output_args = [
            "-b:v", f"{profile.bitrate_k}k",
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-r", str(profile.fps),
            *output_args,
        ]
    else:
        gop = int(args_ns_gop(profile, args))
        output_args = [
            "-b:v", f"{profile.bitrate_k}k",
            "-maxrate", f"{profile.bitrate_k}k",
            "-bufsize", f"{profile.bitrate_k * 2}k",
            "-g", str(gop),
            "-keyint_min", str(gop),
            "-r", str(profile.fps),
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-flush_packets", "1",
            "-muxdelay", "0",
            "-muxpreload", "0",
            "-mpegts_flags", "+resend_headers",
            *output_args,
        ]
    return [*output_args, output_target]


def args_ns_gop(profile: StreamProfile, args: argparse.Namespace) -> int:
    if args.gop_frames is not None:
        return max(1, int(args.gop_frames))
    if args.gop_multiplier is not None:
        return max(1, int(round(profile.fps * args.gop_multiplier)))
    return max(1, int(profile.fps))


def build_ffmpeg_cmd(
    profile: StreamProfile,
    args: argparse.Namespace,
    encoder_name: str,
    source_mode: str,
    write_to_stdout: bool,
    vt_preset: str = "auto",
) -> list[str]:
    encoder = resolve_encoder(encoder_name)
    if encoder == "h264_videotoolbox":
        if vt_preset == "legacy":
            encoder_opts = ["-realtime", "1"]
        elif vt_preset == "current":
            encoder_opts = [
                "-realtime", "1",
                "-prio_speed", "1",
                "-power_efficient", "0",
                "-profile:v", "constrained_baseline",
                "-coder", "cavlc",
                "-max_ref_frames", "1",
            ]
        else:
            encoder_opts = ["-realtime", "1"]
    else:
        encoder_opts = ["-preset", "ultrafast"]
    cmd = [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-nostats",
        "-progress", "pipe:2",
    ]
    if source_mode == "testsrc":
        cmd += [
            "-re",
            "-f", "lavfi",
            "-i", f"testsrc=size={profile.width}x{profile.height}:rate={profile.fps}",
        ]
    else:
        if args.ffmpeg_input_mode == "mjpeg":
            cmd += [
                "-f", "mjpeg",
                "-framerate", str(profile.fps),
                "-i", "-",
            ]
        else:
            cmd += [
                "-f", "image2pipe",
                "-framerate", str(profile.fps),
                "-vcodec", "mjpeg",
                "-i", "-",
            ]
    cmd += ["-c:v", encoder, *encoder_opts]
    cmd += build_ffmpeg_output_args(profile, args, write_to_stdout)
    return cmd


def build_rawvideo_ffmpeg_cmd(
    width: int,
    height: int,
    frame_rate: int,
    encoder_name: str,
    ffmpeg_mode: str,
    bitrate_k: int,
    write_to_stdout: bool,
) -> list[str]:
    encoder = resolve_encoder(encoder_name)
    encoder_opts = (
        ["-realtime", "1", "-allow_sw", "1"]
        if encoder == "h264_videotoolbox"
        else ["-preset", "ultrafast", "-tune", "zerolatency"]
    )
    output_target = "pipe:1" if write_to_stdout else "-"
    if ffmpeg_mode == "service":
        rate_args = [
            "-b:v", "2500k",
            "-r", str(frame_rate),
        ]
        mux_args = ["-pix_fmt", "yuv420p", "-f", "mpegts", "-muxrate", "4000k", "-pcr_period", "20"]
    else:
        rate_args = [
            "-b:v", f"{bitrate_k}k",
            "-maxrate", f"{bitrate_k}k",
            "-bufsize", f"{bitrate_k * 2}k",
            "-g", str(frame_rate),
            "-keyint_min", str(frame_rate),
            "-r", str(frame_rate),
            "-fflags", "nobuffer",
            "-flags", "low_delay",
            "-flush_packets", "1",
            "-muxdelay", "0",
            "-muxpreload", "0",
            "-mpegts_flags", "+resend_headers",
        ]
        mux_args = ["-pix_fmt", "yuv420p", "-f", "mpegts", "-muxrate", f"{max(4000, bitrate_k * 3)}k", "-pcr_period", "20"]
    return [
        "ffmpeg",
        "-y",
        "-hide_banner",
        "-loglevel", "error",
        "-nostats",
        "-progress", "pipe:2",
        "-f", "rawvideo",
        "-pix_fmt", "bgr24",
        "-s:v", f"{width}x{height}",
        "-r", str(frame_rate),
        "-i", "-",
        "-an",
        "-c:v", encoder,
        *encoder_opts,
        *rate_args,
        *mux_args,
        output_target,
    ]


class ReusableThreadingHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = True


class SharedReadRelayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self) -> None:
        with suppress(ConnectionResetError, BrokenPipeError):
            super().handle()

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path != "/live.ts":
            self.send_error(404)
            return
        runner = self.server.runner
        proc = self.server.ffmpeg_proc
        with runner.relay_lock:
            runner.metrics.relay_clients += 1
            runner.metrics.relay_peak_clients = max(runner.metrics.relay_peak_clients, runner.metrics.relay_clients)
        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while not runner.stop_event.is_set():
                chunk = proc.stdout.read(32768)
                if not chunk:
                    break
                self.wfile.write(chunk)
                runner.metrics.relay_bytes_out += len(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            with runner.relay_lock:
                runner.metrics.relay_clients = max(0, runner.metrics.relay_clients - 1)


class FanoutRelay:
    def __init__(self, proc: subprocess.Popen, metrics: Metrics, stop_event: threading.Event, queue_chunks: int):
        self.proc = proc
        self.metrics = metrics
        self.stop_event = stop_event
        self.queue_chunks = queue_chunks
        self.lock = threading.Lock()
        self.subscribers: dict[int, queue.Queue[Optional[bytes]]] = {}
        self.next_id = 1
        self.thread = threading.Thread(target=self._pump, daemon=True)
        self.thread.start()

    def register(self) -> tuple[int, queue.Queue[Optional[bytes]]]:
        q: queue.Queue[Optional[bytes]] = queue.Queue(maxsize=self.queue_chunks)
        with self.lock:
            sid = self.next_id
            self.next_id += 1
            self.subscribers[sid] = q
            self.metrics.relay_clients += 1
            self.metrics.relay_peak_clients = max(self.metrics.relay_peak_clients, self.metrics.relay_clients)
            return sid, q

    def unregister(self, sid: int) -> None:
        with self.lock:
            self.subscribers.pop(sid, None)
            self.metrics.relay_clients = max(0, self.metrics.relay_clients - 1)

    def close(self) -> None:
        with self.lock:
            subscribers = list(self.subscribers.values())
        for q in subscribers:
            with suppress(queue.Full):
                q.put_nowait(None)
        self.thread.join(timeout=1.0)

    def _pump(self) -> None:
        if self.proc.stdout is None:
            return
        while not self.stop_event.is_set():
            chunk = self.proc.stdout.read(32768)
            if not chunk:
                break
            self.metrics.relay_bytes_out += len(chunk)
            with self.lock:
                subscribers = list(self.subscribers.values())
            for q in subscribers:
                while True:
                    try:
                        q.put_nowait(chunk)
                        break
                    except queue.Full:
                        try:
                            dropped = q.get_nowait()
                        except queue.Empty:
                            break
                        if dropped:
                            self.metrics.relay_drop_events += 1
                            self.metrics.relay_drop_bytes += len(dropped)
        with self.lock:
            subscribers = list(self.subscribers.values())
        for q in subscribers:
            with suppress(queue.Full):
                q.put_nowait(None)


class FanoutRelayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def handle(self) -> None:
        with suppress(ConnectionResetError, BrokenPipeError):
            super().handle()

    def log_message(self, fmt: str, *args) -> None:
        return

    def do_GET(self) -> None:
        if self.path != "/live.ts":
            self.send_error(404)
            return
        fanout: FanoutRelay = self.server.fanout_relay
        sid, q = fanout.register()
        self.send_response(200)
        self.send_header("Content-Type", "video/mp2t")
        self.send_header("Connection", "keep-alive")
        self.end_headers()
        try:
            while not fanout.stop_event.is_set():
                try:
                    chunk = q.get(timeout=1.0)
                except queue.Empty:
                    continue
                if chunk is None:
                    break
                self.wfile.write(chunk)
        except (BrokenPipeError, ConnectionResetError):
            pass
        finally:
            fanout.unregister(sid)


class SourceAdapter:
    def __init__(self, args: argparse.Namespace, profile: StreamProfile, metrics: Metrics, frame_store: FrameStore):
        self.args = args
        self.profile = profile
        self.capture_width, self.capture_height = capture_dimensions(args, profile)
        self.metrics = metrics
        self.frame_store = frame_store
        self.stop_event = threading.Event()
        self.capture_error: Optional[str] = None
        self.browser_console: list[dict[str, str]] = []
        self.page_errors: list[str] = []
        self._task: Optional[asyncio.Task] = None
        self._thread: Optional[threading.Thread] = None
        self._decode_thread: Optional[threading.Thread] = None
        self._decode_lock = threading.Lock()
        self._pending_b64: Optional[str] = None
        self._decode_event = threading.Event()
        self.frame_counter = 0

    def start(self) -> None:
        if self.args.source_mode == "overlay":
            if self.args.decode_mode == "worker":
                self._decode_thread = threading.Thread(target=self._decode_loop, daemon=True)
                self._decode_thread.start()
            self._task = asyncio.create_task(self._playwright_capture())
        else:
            self._thread = threading.Thread(target=self._synthetic_source_loop, daemon=True)
            self._thread.start()

    async def stop(self) -> None:
        self.stop_event.set()
        self.frame_store.event.set()
        self._decode_event.set()
        if self._task is not None:
            if not self._task.done():
                self._task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await self._task

    def _emit_frame(self, payload: bytes) -> None:
        ts = now()
        frame = FrameSnapshot(data=payload, frame_id=self.frame_counter, captured_at=ts)
        self.frame_counter += 1
        self.frame_store.push(frame)
        self.metrics.record_source_arrival(ts)

    def _decode_and_emit(self, payload_b64: str) -> None:
        started = time.perf_counter()
        payload = base64.b64decode(payload_b64)
        self.metrics.decode_samples_ms.append((time.perf_counter() - started) * 1000.0)
        self._emit_frame(payload)

    def _decode_loop(self) -> None:
        while not self.stop_event.is_set():
            self._decode_event.wait(0.25)
            if self.stop_event.is_set():
                break
            self._decode_event.clear()
            payload_b64 = None
            with self._decode_lock:
                payload_b64 = self._pending_b64
                self._pending_b64 = None
            if not payload_b64:
                continue
            try:
                self._decode_and_emit(payload_b64)
            except Exception as exc:
                self.capture_error = f"decode_failed:{type(exc).__name__}:{exc}"
                return

    def _synthetic_source_loop(self) -> None:
        if Image is None or ImageDraw is None:
            self.capture_error = "Pillow is required for synthetic source mode"
            return
        fps = float(self.args.synthetic_source_fps or 1.0)
        interval = 1.0 / max(fps, 0.1)
        while not self.stop_event.is_set():
            image = Image.new("RGB", (self.profile.width, self.profile.height), (22, 22, 24))
            draw = ImageDraw.Draw(image)
            draw.text((24, 24), f"source={self.args.source_mode}", fill=(250, 250, 250))
            draw.text((24, 64), f"frame={self.frame_counter}", fill=(120, 220, 255))
            draw.text((24, 104), time.strftime("%H:%M:%S"), fill=(220, 220, 220))
            from io import BytesIO
            buf = BytesIO()
            image.save(buf, format="JPEG", quality=self.profile.jpeg_quality)
            self._emit_frame(buf.getvalue())
            time.sleep(interval)

    async def _playwright_capture(self) -> None:
        from playwright.async_api import async_playwright

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=chromium_args_for_mode(
                        self.args.gpu_mode,
                        self.args.chromium_arg,
                        include_default_args=not self.args.disable_default_chromium_args,
                    ),
                )
                page = await browser.new_page(
                    viewport={"width": self.profile.width, "height": self.profile.height}
                )
                page.on(
                    "console",
                    lambda msg: self.browser_console.append({"type": msg.type, "text": msg.text}),
                )
                page.on("pageerror", lambda error: self.page_errors.append(str(error)))
                await page.goto(self.args.overlay_url, wait_until="domcontentloaded", timeout=20000)
                cdp = await page.context.new_cdp_session(page)

                async def on_frame(event: dict[str, Any]) -> None:
                    if self.stop_event.is_set():
                        return
                    if self.args.decode_mode == "worker":
                        with self._decode_lock:
                            self._pending_b64 = event["data"]
                        self._decode_event.set()
                    else:
                        self._decode_and_emit(event["data"])
                    with suppress(Exception):
                        await cdp.send("Page.screencastFrameAck", {"sessionId": event["sessionId"]})

                cdp.on("Page.screencastFrame", lambda event: asyncio.create_task(on_frame(event)))
                await cdp.send(
                    "Page.startScreencast",
                    {
                        "format": "jpeg",
                        "quality": self.args.screencast_quality,
                        "maxWidth": self.capture_width,
                        "maxHeight": self.capture_height,
                        "everyNthFrame": self.args.every_nth_frame,
                    },
                )
                try:
                    while not self.stop_event.is_set():
                        await asyncio.sleep(0.25)
                finally:
                    with suppress(Exception):
                        await cdp.send("Page.stopScreencast")
                    await page.close()
                    await browser.close()
        except Exception as exc:
            self.capture_error = f"playwright_capture_failed:{type(exc).__name__}:{exc}"


class OverlayCaptureRunner:
    def __init__(self, args: argparse.Namespace, strategy: str):
        self.args = args
        self.strategy = strategy
        self.profile = effective_profile(args)
        self.metrics = Metrics()
        self.frame_store = FrameStore()
        self.stop_event = threading.Event()
        self.proc: Optional[subprocess.Popen] = None
        self.progress_thread: Optional[threading.Thread] = None
        self.scheduler_thread: Optional[threading.Thread] = None
        self.stdout_drain_thread: Optional[threading.Thread] = None
        self.source = SourceAdapter(args, self.profile, self.metrics, self.frame_store)
        self.rate_lock = threading.Lock()
        self.current_scheduler_fps = float(self.args.encode_fps or self.profile.fps)
        self.started_at = 0.0
        self.ended_at = 0.0
        self.speed_ema: Optional[float] = None
        self.zero_speed_streak = 0
        self.last_control_progress_time = 0.0
        self.flush_counter = 0

    def _update_speed_ema(self) -> Optional[float]:
        sample = self.metrics.ffmpeg_speed
        if sample is None:
            return self.speed_ema
        if sample <= 0:
            self.zero_speed_streak += 1
            if self.zero_speed_streak < self.args.zero_speed_persist_samples:
                return self.speed_ema
        else:
            self.zero_speed_streak = 0
        if self.speed_ema is None:
            self.speed_ema = sample
        else:
            alpha = self.args.speed_ema_alpha
            self.speed_ema = (alpha * sample) + ((1.0 - alpha) * self.speed_ema)
        return self.speed_ema

    def _speed_control_rate(self, current_rate: float, now_ts: float) -> float:
        speed_ema = self._update_speed_ema()
        recent_block_ms = self.metrics.stdin_block_samples_ms[-1] if self.metrics.stdin_block_samples_ms else 0.0
        last_progress = self.metrics.ffmpeg_progress_times[-1] if self.metrics.ffmpeg_progress_times else 0.0
        no_progress_ms = (now_ts - last_progress) * 1000.0 if last_progress else 1e9

        new_rate = current_rate
        has_fresh_progress = (
            last_progress > 0
            and last_progress != self.last_control_progress_time
            and no_progress_ms <= self.args.progress_timeout_ms
        )
        if speed_ema is not None and has_fresh_progress:
            error = speed_ema - self.args.target_ffmpeg_speed
            scale = 1.0 - (self.args.speed_control_kp * error)
            scale = max(1.0 - self.args.max_rate_step_ratio, min(1.0 + self.args.max_rate_step_ratio, scale))
            new_rate *= scale
            self.last_control_progress_time = last_progress

        if recent_block_ms > self.args.stdin_backoff_ms:
            block_scale = 1.0 - min(
                self.args.max_rate_step_ratio,
                self.args.stdin_control_gain * (recent_block_ms / max(self.args.stdin_backoff_ms, 0.1)),
            )
            new_rate *= block_scale

        if no_progress_ms > self.args.progress_timeout_ms:
            new_rate *= 1.0 + min(self.args.search_growth_ratio, self.args.max_rate_step_ratio)

        return max(self.args.min_encode_fps, min(self.args.max_encode_fps, new_rate))

    def start(self) -> None:
        self.started_at = now()
        self.proc = subprocess.Popen(
            build_ffmpeg_cmd(
                self.profile,
                self.args,
                self.args.encoder,
                "synthetic",
                write_to_stdout=False,
                vt_preset=self.args.vt_preset,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.progress_thread = threading.Thread(target=self._pump_ffmpeg_logs, daemon=True)
        self.progress_thread.start()
        self.source.start()
        self.scheduler_thread = threading.Thread(target=self._scheduler_loop, daemon=True)
        self.scheduler_thread.start()

    def _pump_ffmpeg_logs(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for raw in iter(self.proc.stderr.readline, b""):
            if self.stop_event.is_set():
                break
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            key, sep, value = line.partition("=")
            if not sep or key not in FFMPEG_PROGRESS_KEYS:
                continue
            if key == "speed":
                self.metrics.ffmpeg_speed = safe_float(value.replace("x", ""))
                if self.metrics.ffmpeg_speed is not None:
                    self.metrics.ffmpeg_speed_samples.append(self.metrics.ffmpeg_speed)
                    self.metrics.ffmpeg_progress_times.append(now())
            elif key == "fps":
                self.metrics.ffmpeg_fps = safe_float(value)
                if self.metrics.ffmpeg_fps is not None:
                    self.metrics.ffmpeg_fps_samples.append(self.metrics.ffmpeg_fps)
                    self.metrics.ffmpeg_progress_times.append(now())
            elif key == "bitrate":
                self.metrics.ffmpeg_bitrate_kbps = safe_float(value.replace("kbits/s", "").strip())
            elif key == "drop_frames":
                with suppress(ValueError):
                    self.metrics.ffmpeg_drop_frames = int(value)
            elif key == "dup_frames":
                with suppress(ValueError):
                    self.metrics.ffmpeg_dup_frames = int(value)
            elif key == "out_time_ms":
                self.metrics.last_progress_at = now()
                self.metrics.ffmpeg_progress_times.append(now())

    def _scheduler_rate(self) -> float:
        with self.rate_lock:
            return self.current_scheduler_fps

    def _set_scheduler_rate(self, value: float) -> None:
        clipped = max(self.args.min_encode_fps, min(self.args.max_encode_fps, value))
        with self.rate_lock:
            if abs(clipped - self.current_scheduler_fps) >= 0.05:
                self.metrics.adaptive_rate_changes += 1
            self.current_scheduler_fps = clipped

    def _scheduler_loop(self) -> None:
        assert self.proc is not None and self.proc.stdin is not None
        next_tick = now()
        last_submitted_id = -1
        interpolation_flip = False
        burst_remaining = 0
        burst_anchor: Optional[FrameSnapshot] = None

        while not self.stop_event.is_set():
            rate = self._scheduler_rate()
            interval = 1.0 / max(rate, 0.1)
            next_tick += interval
            sleep_for = next_tick - now()
            if sleep_for > 0:
                time.sleep(sleep_for)
            else:
                next_tick = now()

            latest, previous = self.frame_store.snapshot()
            chosen = latest
            repeated = False
            submit_rate = rate

            if latest is None:
                continue

            frame_age_ms = (now() - latest.captured_at) * 1000.0
            is_new_frame = latest.frame_id != last_submitted_id
            control_now = now()

            if self.strategy == "naive_repeat_last":
                repeated = not is_new_frame
            elif self.strategy == "adaptive_repeat_last":
                repeated = not is_new_frame
                new_rate = rate
                if repeated:
                    if frame_age_ms > self.args.repeat_last_after_idle_ms:
                        new_rate = min(self.args.max_encode_fps, rate + self.args.adaptive_step_up)
                    if self.metrics.ffmpeg_speed is not None and self.metrics.ffmpeg_speed > 1.1:
                        new_rate = max(self.args.min_encode_fps, new_rate - self.args.adaptive_step_down)
                    if self.metrics.stdin_block_samples_ms:
                        recent_block = self.metrics.stdin_block_samples_ms[-1]
                        if recent_block > self.args.stdin_backoff_ms:
                            new_rate = max(self.args.min_encode_fps, new_rate - self.args.adaptive_step_down * 2.0)
                else:
                    if self.metrics.ffmpeg_speed is not None and self.metrics.ffmpeg_speed < 0.95:
                        new_rate = max(self.args.min_encode_fps, rate - self.args.adaptive_step_down)
                    elif self.metrics.ffmpeg_speed is not None and self.metrics.ffmpeg_speed > 1.05:
                        new_rate = min(self.args.max_encode_fps, rate + self.args.adaptive_step_up * 0.5)
                self._set_scheduler_rate(new_rate)
                submit_rate = self._scheduler_rate()
            elif self.strategy == "frame_interpolation_stub":
                if is_new_frame:
                    chosen = latest
                    interpolation_flip = False
                else:
                    repeated = True
                    if previous is not None and frame_age_ms >= self.args.repeat_last_after_idle_ms:
                        chosen = previous if interpolation_flip else latest
                        interpolation_flip = not interpolation_flip
                        self.metrics.interpolated_submits += 1
            elif self.strategy == "burst_smoothing":
                if is_new_frame:
                    burst_anchor = latest
                    burst_remaining = max(1, self.args.burst_smoothing_window)
                elif burst_anchor is not None and burst_remaining > 0:
                    chosen = burst_anchor
                    repeated = True
                    burst_remaining -= 1
                    self.metrics.burst_smoothed_submits += 1
                else:
                    repeated = True
            elif self.strategy == "speed_control_repeat":
                new_rate = self._speed_control_rate(rate, control_now)
                self._set_scheduler_rate(new_rate)
                submit_rate = self._scheduler_rate()
                repeated = not is_new_frame
            elif self.strategy == "speed_control_burst_smoothing":
                new_rate = self._speed_control_rate(rate, control_now)
                self._set_scheduler_rate(new_rate)
                submit_rate = self._scheduler_rate()
                if is_new_frame:
                    burst_anchor = latest
                    burst_remaining = max(1, self.args.burst_smoothing_window)
                elif burst_anchor is not None and burst_remaining > 0:
                    chosen = burst_anchor
                    repeated = True
                    burst_remaining -= 1
                    self.metrics.burst_smoothed_submits += 1
                else:
                    repeated = True
            elif self.strategy == "speed_control_interpolation":
                new_rate = self._speed_control_rate(rate, control_now)
                self._set_scheduler_rate(new_rate)
                submit_rate = self._scheduler_rate()
                if is_new_frame:
                    chosen = latest
                    interpolation_flip = False
                else:
                    repeated = True
                    if previous is not None:
                        chosen = previous if interpolation_flip else latest
                        interpolation_flip = not interpolation_flip
                        self.metrics.interpolated_submits += 1
            else:
                raise RuntimeError(f"unsupported strategy: {self.strategy}")

            if repeated:
                self.metrics.source_idle_repeats += 1
            if not repeated and chosen.frame_id == last_submitted_id:
                self.metrics.duplicate_skip_count += 1

            try:
                write_started = time.perf_counter()
                self.proc.stdin.write(chosen.data)
                self.flush_counter += 1
                should_flush = True
                if self.args.stdin_flush_mode == "none":
                    should_flush = False
                elif self.args.stdin_flush_mode == "batched":
                    should_flush = (self.flush_counter % max(1, self.args.stdin_flush_every)) == 0
                if should_flush:
                    self.proc.stdin.flush()
                block_ms = (time.perf_counter() - write_started) * 1000.0
                submitted_at = now()
                self.metrics.record_submit(submitted_at, block_ms, submit_rate)
                if chosen.frame_id != last_submitted_id:
                    last_submitted_id = chosen.frame_id
            except Exception:
                break

    async def stop(self) -> None:
        self.stop_event.set()
        await self.source.stop()
        self.frame_store.event.set()
        self.ended_at = now()
        if self.proc is not None:
            with suppress(Exception):
                if self.proc.stdin is not None:
                    self.proc.stdin.close()
            with suppress(Exception):
                self.proc.kill()

    def result(self) -> dict[str, Any]:
        seconds = self.args.seconds
        effective_gaps = list(self.metrics.source_idle_gaps_ms)
        if self.metrics.source_arrivals:
            trailing_gap_ms = max(0.0, (self.ended_at - self.metrics.source_arrivals[-1]) * 1000.0)
            effective_gaps.append(trailing_gap_ms)
        return {
            "benchmark_mode": "overlay_capture_benchmark",
            "strategy": self.strategy,
            "service_config_preset": self.args.service_config_preset,
            "source_mode": self.args.source_mode,
            "gpu_mode": self.args.gpu_mode,
            "ffmpeg_mode": self.args.ffmpeg_mode,
            "target_bitrate_k": self.profile.bitrate_k,
            "every_nth_frame": self.args.every_nth_frame,
            "screencast_quality": self.args.screencast_quality,
            "decode_mode": self.args.decode_mode,
            "viewport_width": self.profile.width,
            "viewport_height": self.profile.height,
            "capture_width": self.source.capture_width,
            "capture_height": self.source.capture_height,
            "source_frame_count": self.metrics.source_frame_count,
            "source_fps": round(self.metrics.source_fps(seconds), 3),
            "avg_inter_frame_ms": round(Metrics._avg(self.metrics.source_intervals_ms), 3),
            "max_inter_frame_gap_ms": round(Metrics._max(self.metrics.source_intervals_ms), 3),
            "idle_gap_histogram": self.metrics.idle_gap_histogram(effective_gaps),
            "submit_frame_count": self.metrics.submit_frame_count,
            "submit_fps": round(self.metrics.submit_fps(seconds), 3),
            "source_idle_repeats": self.metrics.source_idle_repeats,
            "stdin_block_avg_ms": round(Metrics._avg(self.metrics.stdin_block_samples_ms), 3),
            "stdin_block_max_ms": round(Metrics._max(self.metrics.stdin_block_samples_ms), 3),
            "decode_avg_ms": round(Metrics._avg(self.metrics.decode_samples_ms), 3),
            "decode_max_ms": round(Metrics._max(self.metrics.decode_samples_ms), 3),
            "trailing_idle_gap_ms": round(effective_gaps[-1], 3) if effective_gaps else 0.0,
            "ffmpeg_speed_avg": round(Metrics._avg(self.metrics.ffmpeg_speed_samples), 3),
            "ffmpeg_speed_max": round(Metrics._max(self.metrics.ffmpeg_speed_samples), 3),
            "ffmpeg_speed_ema_final": round(self.speed_ema, 3) if self.speed_ema is not None else None,
            "ffmpeg_speed": self.metrics.ffmpeg_speed,
            "ffmpeg_fps": self.metrics.ffmpeg_fps,
            "ffmpeg_bitrate_kbps": self.metrics.ffmpeg_bitrate_kbps,
            "ffmpeg_dup_frames": self.metrics.ffmpeg_dup_frames,
            "ffmpeg_drop_frames": self.metrics.ffmpeg_drop_frames,
            "scheduler_rate_avg_fps": round(Metrics._avg(self.metrics.scheduler_rate_samples), 3),
            "scheduler_rate_stddev_fps": round(Metrics._stddev(self.metrics.scheduler_rate_samples), 3),
            "stability_score": self.metrics.stability_score(
                float(self.args.encode_fps or self.profile.fps),
                effective_gaps,
            ),
            "duplicate_skip_count": self.metrics.duplicate_skip_count,
            "burst_smoothed_submits": self.metrics.burst_smoothed_submits,
            "interpolated_submits": self.metrics.interpolated_submits,
            "adaptive_rate_changes": self.metrics.adaptive_rate_changes,
            "capture_error": self.source.capture_error,
            "browser_console_tail": self.source.browser_console[-10:],
            "page_errors": self.source.page_errors[-10:],
        }


class WebRTCCaptureRunner:
    def __init__(self, args: argparse.Namespace, scenario: str):
        self.args = args
        self.scenario = scenario
        self.profile = effective_profile(args)
        self.metrics = Metrics()
        self.capture_error: Optional[str] = None
        self.browser_console: list[dict[str, str]] = []
        self.page_errors: list[str] = []
        self.proc: Optional[subprocess.Popen] = None
        self.progress_thread: Optional[threading.Thread] = None
        self.stdout_thread: Optional[threading.Thread] = None
        self.ts_bytes_out = 0
        self.ts_chunks = 0
        self.started_at = 0.0
        self.ended_at = 0.0
        self.last_frame_pts_seconds: Optional[float] = None
        self.estimated_dropped_frames = 0
        self.page_verification: dict[str, Any] = {}

    async def run(self) -> dict[str, Any]:
        self.started_at = now()
        try:
            from aiortc import RTCPeerConnection, RTCSessionDescription
        except ImportError as exc:
            self.capture_error = f"aiortc_missing:{exc}"
            self.ended_at = now()
            return self.result()

        from playwright.async_api import async_playwright

        backend_pc = RTCPeerConnection()
        browser_pc_started = asyncio.Event()
        first_frame_received = asyncio.Event()
        track_tasks: list[asyncio.Task] = []

        @backend_pc.on("track")
        def on_track(track):
            if track.kind != "video":
                return
            task = asyncio.create_task(self._consume_track(track, first_frame_received))
            track_tasks.append(task)

        try:
            async with async_playwright() as playwright:
                browser = await playwright.chromium.launch(
                    headless=True,
                    args=chromium_args_for_mode(self.args.gpu_mode, self.args.chromium_arg),
                )
                page = await browser.new_page(viewport={"width": self.profile.width, "height": self.profile.height})
                page.on("console", lambda msg: self.browser_console.append({"type": msg.type, "text": msg.text}))
                page.on("pageerror", lambda error: self.page_errors.append(str(error)))
                await self._prepare_scenario_page(page)
                self.page_verification = await self._collect_page_verification(page)
                offer = await page.evaluate(
                    """
                    async ({ frameRate }) => {
                        const waitForIce = (pc) => {
                            if (pc.iceGatheringState === 'complete') return Promise.resolve();
                            return new Promise((resolve) => {
                                const onChange = () => {
                                    if (pc.iceGatheringState === 'complete') {
                                        pc.removeEventListener('icegatheringstatechange', onChange);
                                        resolve();
                                    }
                                };
                                pc.addEventListener('icegatheringstatechange', onChange);
                            });
                        };
                        const canvas = document.getElementById('mapping-canvas');
                        if (!canvas || typeof canvas.captureStream !== 'function') {
                            throw new Error('captureStream canvas unavailable');
                        }
                        const stream = canvas.captureStream(frameRate);
                        const track = stream.getVideoTracks()[0];
                        if (track) {
                            track.contentHint = 'detail';
                        }
                        const pc = new RTCPeerConnection();
                        stream.getTracks().forEach((mediaTrack) => pc.addTrack(mediaTrack, stream));
                        window.__harnessWebRTCPeer = pc;
                        window.__harnessWebRTCStream = stream;
                        const offer = await pc.createOffer();
                        await pc.setLocalDescription(offer);
                        await waitForIce(pc);
                        const settings = track ? track.getSettings() : null;
                        return {
                            sdp: pc.localDescription.sdp,
                            type: pc.localDescription.type,
                            trackSettings: settings,
                        };
                    }
                    """,
                    {"frameRate": self.args.webrtc_capture_fps},
                )
                await backend_pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
                answer = await backend_pc.createAnswer()
                await backend_pc.setLocalDescription(answer)
                await self._wait_for_ice_complete(backend_pc)
                await page.evaluate(
                    """
                    async ({ sdp, type }) => {
                        const pc = window.__harnessWebRTCPeer;
                        if (!pc) {
                            throw new Error('browser peer connection missing');
                        }
                        await pc.setRemoteDescription({ sdp, type });
                    }
                    """,
                    {"sdp": backend_pc.localDescription.sdp, "type": backend_pc.localDescription.type},
                )
                browser_pc_started.set()
                await asyncio.sleep(self.args.seconds)
                await page.evaluate(
                    """
                    () => {
                        if (window.__harnessWebRTCStream) {
                            window.__harnessWebRTCStream.getTracks().forEach((track) => track.stop());
                            window.__harnessWebRTCStream = null;
                        }
                        if (window.__harnessWebRTCPeer) {
                            window.__harnessWebRTCPeer.close();
                            window.__harnessWebRTCPeer = null;
                        }
                    }
                    """
                )
                await browser.close()
        except Exception as exc:
            self.capture_error = f"{type(exc).__name__}:{exc}"
        finally:
            for task in track_tasks:
                if not task.done():
                    task.cancel()
                with suppress(asyncio.CancelledError, Exception):
                    await task
            await backend_pc.close()
            self.ended_at = now()
            await self._stop_ffmpeg()
        return self.result()

    async def _prepare_scenario_page(self, page) -> None:
        if self.scenario == "overlay_canvas":
            await page.goto(self.args.overlay_url, wait_until="domcontentloaded", timeout=20000)
            await asyncio.sleep(3.0)
            return
        if self.scenario == "synthetic_canvas":
            await page.set_content(SYNTHETIC_CANVAS_HTML, wait_until="load")
            await asyncio.sleep(1.0)
            return
        if self.scenario == "synthetic_composited":
            await page.set_content(SYNTHETIC_COMPOSITED_HTML, wait_until="load")
            await asyncio.sleep(1.0)
            return
        raise RuntimeError(f"unsupported WebRTC scenario: {self.scenario}")

    async def _collect_page_verification(self, page) -> dict[str, Any]:
        verification = {
            "playwright_page_url": page.url,
        }
        page_state = await page.evaluate(
            """
            () => {
                const href = document.location.href;
                const params = new URL(href).searchParams;
                const mappingCanvas = document.getElementById('mapping-canvas');
                const animationHost = document.getElementById('mapping-animation-host');
                const widgetCandidates = [
                    document.getElementById('widgets-container'),
                    document.querySelector('.widget'),
                    document.querySelector('.weather-widget'),
                    document.querySelector('.time-widget'),
                    document.querySelector('.spotify-widget'),
                ].filter(Boolean);
                const canvases = Array.from(document.querySelectorAll('canvas')).map((canvas, index) => ({
                    index,
                    id: canvas.id || null,
                    width: canvas.width,
                    height: canvas.height,
                }));
                return {
                    document_location_href: href,
                    config_id: params.get('config_id'),
                    controls: params.get('controls'),
                    has_config_id_2: params.get('config_id') === '2',
                    mapping_canvas_exists: !!mappingCanvas,
                    mapping_canvas_width: mappingCanvas ? mappingCanvas.width : null,
                    mapping_canvas_height: mappingCanvas ? mappingCanvas.height : null,
                    mapping_animation_host_exists: !!animationHost,
                    widgets_present: widgetCandidates.length > 0,
                    widget_candidate_count: widgetCandidates.length,
                    canvas_count: canvases.length,
                    canvases,
                };
            }
            """
        )
        verification.update(page_state)
        return verification

    async def _consume_track(self, track, first_frame_received: asyncio.Event) -> None:
        while True:
            frame = await track.recv()
            ts = now()
            self.metrics.record_source_arrival(ts)
            if not first_frame_received.is_set():
                first_frame_received.set()

            pts_seconds = None
            if frame.pts is not None and frame.time_base is not None:
                pts_seconds = float(frame.pts * frame.time_base)
                if self.last_frame_pts_seconds is not None:
                    delta = pts_seconds - self.last_frame_pts_seconds
                    expected = 1.0 / max(float(self.args.webrtc_capture_fps), 0.1)
                    if delta > expected * 1.5:
                        estimated = max(0, int(round(delta / expected)) - 1)
                        self.estimated_dropped_frames += estimated
                self.last_frame_pts_seconds = pts_seconds

            frame_array = frame.to_ndarray(format="bgr24")
            if self.proc is None:
                self._start_ffmpeg(frame_array.shape[1], frame_array.shape[0])
            try:
                assert self.proc is not None and self.proc.stdin is not None
                write_started = time.perf_counter()
                self.proc.stdin.write(frame_array.tobytes())
                self.proc.stdin.flush()
                block_ms = (time.perf_counter() - write_started) * 1000.0
                self.metrics.record_submit(ts, block_ms, float(self.args.webrtc_capture_fps))
            except Exception as exc:
                self.capture_error = f"ffmpeg_write_failed:{type(exc).__name__}:{exc}"
                break

    def _start_ffmpeg(self, width: int, height: int) -> None:
        self.proc = subprocess.Popen(
            build_rawvideo_ffmpeg_cmd(
                width=width,
                height=height,
                frame_rate=int(self.args.webrtc_capture_fps),
                encoder_name=self.args.encoder,
                ffmpeg_mode=self.args.ffmpeg_mode,
                bitrate_k=self.profile.bitrate_k,
                write_to_stdout=True,
            ),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.progress_thread = threading.Thread(target=self._pump_ffmpeg_logs, daemon=True)
        self.progress_thread.start()
        self.stdout_thread = threading.Thread(target=self._pump_ffmpeg_stdout, daemon=True)
        self.stdout_thread.start()

    def _pump_ffmpeg_logs(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for raw in iter(self.proc.stderr.readline, b""):
            line = raw.decode("utf-8", errors="replace").strip()
            if not line:
                continue
            key, sep, value = line.partition("=")
            if not sep or key not in FFMPEG_PROGRESS_KEYS:
                continue
            stamp = now()
            if key == "speed":
                self.metrics.ffmpeg_speed = safe_float(value.replace("x", ""))
                if self.metrics.ffmpeg_speed is not None:
                    self.metrics.ffmpeg_speed_samples.append(self.metrics.ffmpeg_speed)
                    self.metrics.ffmpeg_progress_times.append(stamp)
            elif key == "fps":
                self.metrics.ffmpeg_fps = safe_float(value)
                if self.metrics.ffmpeg_fps is not None:
                    self.metrics.ffmpeg_fps_samples.append(self.metrics.ffmpeg_fps)
                    self.metrics.ffmpeg_progress_times.append(stamp)
            elif key == "bitrate":
                self.metrics.ffmpeg_bitrate_kbps = safe_float(value.replace("kbits/s", "").strip())
            elif key == "drop_frames":
                with suppress(ValueError):
                    self.metrics.ffmpeg_drop_frames = int(value)
            elif key == "dup_frames":
                with suppress(ValueError):
                    self.metrics.ffmpeg_dup_frames = int(value)

    def _pump_ffmpeg_stdout(self) -> None:
        assert self.proc is not None and self.proc.stdout is not None
        for chunk in iter(lambda: self.proc.stdout.read(32768), b""):
            if not chunk:
                break
            self.ts_bytes_out += len(chunk)
            self.ts_chunks += 1

    async def _wait_for_ice_complete(self, peer_connection) -> None:
        if peer_connection.iceGatheringState == "complete":
            return
        completed = asyncio.Event()

        @peer_connection.on("icegatheringstatechange")
        async def on_ice():
            if peer_connection.iceGatheringState == "complete":
                completed.set()

        with suppress(asyncio.TimeoutError):
            await asyncio.wait_for(completed.wait(), timeout=5)

    async def _stop_ffmpeg(self) -> None:
        if self.proc is None:
            return
        with suppress(Exception):
            if self.proc.stdin is not None:
                self.proc.stdin.close()
        with suppress(Exception):
            self.proc.kill()

    def result(self) -> dict[str, Any]:
        seconds = max(self.ended_at - self.started_at, self.args.seconds)
        trailing_gap_ms = 0.0
        if self.metrics.source_arrivals:
            trailing_gap_ms = max(0.0, (self.ended_at - self.metrics.source_arrivals[-1]) * 1000.0)
        effective_gaps = list(self.metrics.source_idle_gaps_ms)
        if trailing_gap_ms:
            effective_gaps.append(trailing_gap_ms)
        smoothness = "poor"
        if self.metrics.source_fps(seconds) >= 10.0 and Metrics._max(effective_gaps) < 500.0:
            smoothness = "good"
        elif self.metrics.source_fps(seconds) >= 5.0 and Metrics._max(effective_gaps) < 1000.0:
            smoothness = "moderate"
        return {
            "benchmark_mode": "webrtc_capture_benchmark",
            "scenario": self.scenario,
            "page_verification": self.page_verification,
            "source_fps": round(self.metrics.source_fps(seconds), 3),
            "source_frame_count": self.metrics.source_frame_count,
            "avg_inter_frame_ms": round(Metrics._avg(self.metrics.source_intervals_ms), 3),
            "max_inter_frame_gap_ms": round(Metrics._max(effective_gaps), 3),
            "frame_interval_histogram": self.metrics.idle_gap_histogram(effective_gaps),
            "backend_submit_fps": round(self.metrics.submit_fps(seconds), 3),
            "estimated_dropped_frames": self.estimated_dropped_frames,
            "ffmpeg_speed_avg": round(Metrics._avg(self.metrics.ffmpeg_speed_samples), 3),
            "ffmpeg_speed_max": round(Metrics._max(self.metrics.ffmpeg_speed_samples), 3),
            "ffmpeg_fps": round(Metrics._avg(self.metrics.ffmpeg_fps_samples), 3),
            "ffmpeg_bitrate_kbps": self.metrics.ffmpeg_bitrate_kbps,
            "stdin_block_avg_ms": round(Metrics._avg(self.metrics.stdin_block_samples_ms), 3),
            "stdin_block_max_ms": round(Metrics._max(self.metrics.stdin_block_samples_ms), 3),
            "ts_bytes_out": self.ts_bytes_out,
            "ts_chunks": self.ts_chunks,
            "trailing_idle_gap_ms": round(trailing_gap_ms, 3),
            "visual_smoothness": smoothness,
            "capture_error": self.capture_error,
            "browser_console_tail": self.browser_console[-10:],
            "page_errors": self.page_errors[-10:],
        }


class RelayBroadcastRunner:
    def __init__(self, args: argparse.Namespace):
        self.args = args
        self.profile = effective_profile(args)
        self.metrics = Metrics()
        self.stop_event = threading.Event()
        self.proc: Optional[subprocess.Popen] = None
        self.relay_server: Optional[ReusableThreadingHTTPServer] = None
        self.relay_thread: Optional[threading.Thread] = None
        self.progress_thread: Optional[threading.Thread] = None
        self.relay_lock = threading.Lock()
        self.fanout: Optional[FanoutRelay] = None
        self.stream_port = args.stream_port or reserve_free_port()
        self.stream_url = f"http://{local_ip()}:{self.stream_port}/live.ts"

    def start(self) -> None:
        self.proc = subprocess.Popen(
            build_ffmpeg_cmd(
                self.profile,
                self.args,
                self.args.encoder,
                "testsrc",
                write_to_stdout=True,
                vt_preset=self.args.vt_preset,
            ),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            bufsize=0,
        )
        self.progress_thread = threading.Thread(target=self._pump_ffmpeg_logs, daemon=True)
        self.progress_thread.start()
        handler = SharedReadRelayHandler if self.args.relay_mode == "shared-read" else FanoutRelayHandler
        self.relay_server = ReusableThreadingHTTPServer(("", self.stream_port), handler)
        self.relay_server.runner = self
        if self.args.relay_mode == "shared-read":
            self.relay_server.ffmpeg_proc = self.proc
        else:
            self.fanout = FanoutRelay(self.proc, self.metrics, self.stop_event, self.args.fanout_queue_chunks)
            self.relay_server.fanout_relay = self.fanout
        self.relay_thread = threading.Thread(target=self.relay_server.serve_forever, daemon=True)
        self.relay_thread.start()

    def _pump_ffmpeg_logs(self) -> None:
        assert self.proc is not None and self.proc.stderr is not None
        for raw in iter(self.proc.stderr.readline, b""):
            if self.stop_event.is_set():
                break
            line = raw.decode("utf-8", errors="replace").strip()
            key, sep, value = line.partition("=")
            if not sep or key not in FFMPEG_PROGRESS_KEYS:
                continue
            if key == "speed":
                self.metrics.ffmpeg_speed = safe_float(value.replace("x", ""))
            elif key == "fps":
                self.metrics.ffmpeg_fps = safe_float(value)
            elif key == "bitrate":
                self.metrics.ffmpeg_bitrate_kbps = safe_float(value.replace("kbits/s", "").strip())

    async def stop(self) -> None:
        self.stop_event.set()
        if self.fanout is not None:
            self.fanout.close()
        if self.relay_server is not None:
            with suppress(Exception):
                self.relay_server.shutdown()
                self.relay_server.server_close()
        if self.proc is not None:
            with suppress(Exception):
                self.proc.kill()

    def result(self, clients: list[ClientStats]) -> dict[str, Any]:
        bytes_per_client = [client.bytes_in for client in clients]
        fairness = (min(bytes_per_client) / max(bytes_per_client)) if bytes_per_client and max(bytes_per_client) else 0.0
        return {
            "benchmark_mode": "relay_broadcast_benchmark",
            "service_config_preset": self.args.service_config_preset,
            "relay_mode": self.args.relay_mode,
            "stream_url": self.stream_url,
            "ffmpeg_speed": self.metrics.ffmpeg_speed,
            "ffmpeg_fps": self.metrics.ffmpeg_fps,
            "ffmpeg_bitrate_kbps": self.metrics.ffmpeg_bitrate_kbps,
            "relay_peak_clients": self.metrics.relay_peak_clients,
            "relay_bytes_out": self.metrics.relay_bytes_out,
            "relay_drop_events": self.metrics.relay_drop_events,
            "relay_drop_bytes": self.metrics.relay_drop_bytes,
            "client_fairness_ratio": round(fairness, 4),
            "clients": [asdict(client) for client in clients],
        }


async def relay_sink_client(url: str, seconds: float, name: str) -> ClientStats:
    stats = ClientStats(name=name)
    deadline = now() + seconds
    timeout = aiohttp.ClientTimeout(total=None, connect=3)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        while now() < deadline:
            stats.reconnects += 1
            try:
                async with session.get(url) as response:
                    if response.status != 200:
                        stats.errors.append(f"http_{response.status}")
                        await asyncio.sleep(0.2)
                        continue
                    while now() < deadline:
                        remaining = deadline - now()
                        if remaining <= 0:
                            break
                        try:
                            chunk = await asyncio.wait_for(
                                response.content.read(32768),
                                timeout=min(1.0, remaining),
                            )
                        except asyncio.TimeoutError:
                            stats.read_timeouts += 1
                            continue
                        if not chunk:
                            break
                        stats.bytes_in += len(chunk)
                        stats.chunks += 1
            except Exception as exc:
                stats.errors.append(f"{type(exc).__name__}:{exc}")
                await asyncio.sleep(0.2)
    return stats


def render_ranked_table(results: list[dict[str, Any]]) -> str:
    ranked = sorted(results, key=lambda item: item.get("stability_score", 0.0), reverse=True)
    headers = ["strategy", "source_fps", "submit_fps", "ffmpeg_speed_avg", "ffmpeg_speed_max", "idle_gaps", "stability_score"]
    rows = [headers]
    for item in ranked:
        idle_long = sum(
            count
            for label, count in item["idle_gap_histogram"].items()
            if label.startswith("<= 1000ms") or label.startswith("<= 2000ms") or label.startswith("<= 5000ms") or label.startswith("> ")
        )
        rows.append([
            item["strategy"],
            f"{item['source_fps']:.2f}",
            f"{item['submit_fps']:.2f}",
            f"{item['ffmpeg_speed_avg']:.2f}",
            f"{item['ffmpeg_speed_max']:.2f}",
            str(idle_long),
            f"{item['stability_score']:.2f}",
        ])
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    rendered = []
    for idx, row in enumerate(rows):
        rendered.append("| " + " | ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) + " |")
        if idx == 0:
            rendered.append("|-" + "-|-".join("-" * width for width in widths) + "-|")
    best = ranked[0]["strategy"] if ranked else "n/a"
    rendered.append(f"best_strategy={best}")
    return "\n".join(rendered)


def render_service_config_overlay_table(results: list[dict[str, Any]]) -> str:
    headers = [
        "config",
        "source_fps",
        "submit_fps",
        "ffmpeg_speed_avg",
        "ffmpeg_speed_max",
        "max_gap_ms",
        "capture",
        "relay",
    ]
    rows = [headers]
    for item in results:
        rows.append([
            item.get("service_config_preset", "custom"),
            f"{item['source_fps']:.2f}",
            f"{item['submit_fps']:.2f}",
            f"{item['ffmpeg_speed_avg']:.2f}",
            f"{item['ffmpeg_speed_max']:.2f}",
            f"{item['max_inter_frame_gap_ms']:.1f}",
            f"{item['capture_width']}x{item['capture_height']}",
            item.get("relay_mode", "n/a"),
        ])
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    rendered = []
    for idx, row in enumerate(rows):
        rendered.append("| " + " | ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) + " |")
        if idx == 0:
            rendered.append("|-" + "-|-".join("-" * width for width in widths) + "-|")
    return "\n".join(rendered)


def render_service_config_relay_table(results: list[dict[str, Any]]) -> str:
    headers = ["config", "relay_mode", "fairness", "ffmpeg_speed", "ffmpeg_fps", "bytes_out"]
    rows = [headers]
    for item in results:
        rows.append([
            item.get("service_config_preset", "custom"),
            item["relay_mode"],
            f"{item['client_fairness_ratio']:.4f}",
            f"{(item['ffmpeg_speed'] or 0.0):.2f}",
            f"{(item['ffmpeg_fps'] or 0.0):.2f}",
            str(item["relay_bytes_out"]),
        ])
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    rendered = []
    for idx, row in enumerate(rows):
        rendered.append("| " + " | ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) + " |")
        if idx == 0:
            rendered.append("|-" + "-|-".join("-" * width for width in widths) + "-|")
    return "\n".join(rendered)


def render_webrtc_table(results: list[dict[str, Any]]) -> str:
    headers = [
        "scenario",
        "source_fps",
        "backend_submit_fps",
        "ffmpeg_speed_avg",
        "estimated_dropped_frames",
        "max_inter_frame_gap_ms",
        "visual_smoothness",
    ]
    rows = [headers]
    for item in results:
        rows.append([
            item["scenario"],
            f"{item['source_fps']:.2f}",
            f"{item['backend_submit_fps']:.2f}",
            f"{item['ffmpeg_speed_avg']:.2f}",
            str(item["estimated_dropped_frames"]),
            f"{item['max_inter_frame_gap_ms']:.1f}",
            item["visual_smoothness"],
        ])
    widths = [max(len(row[idx]) for row in rows) for idx in range(len(headers))]
    rendered = []
    for idx, row in enumerate(rows):
        rendered.append("| " + " | ".join(cell.ljust(widths[col]) for col, cell in enumerate(row)) + " |")
        if idx == 0:
            rendered.append("|-" + "-|-".join("-" * width for width in widths) + "-|")
    return "\n".join(rendered)


async def run_overlay_capture_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    strategies = args.strategy or ["speed_control_repeat", "speed_control_burst_smoothing", "speed_control_interpolation"]
    results: list[dict[str, Any]] = []
    for strategy in strategies:
        runner = OverlayCaptureRunner(args, strategy)
        runner.start()
        await asyncio.sleep(args.seconds)
        await runner.stop()
        results.append(runner.result())
        await asyncio.sleep(0.5)
    return {
        "benchmark_mode": "overlay_capture_benchmark",
        "runs": results,
        "ranked_table": render_ranked_table(results),
    }


def apply_service_config_preset(args: argparse.Namespace, preset_name: str) -> argparse.Namespace:
    preset = SERVICE_CONFIG_PRESETS[preset_name]
    next_args = argparse.Namespace(**vars(args))
    next_args.service_config_preset = preset.name
    next_args.viewport_width = preset.viewport_width
    next_args.viewport_height = preset.viewport_height
    next_args.capture_width = preset.capture_width
    next_args.capture_height = preset.capture_height
    next_args.stream_fps = preset.frame_rate
    next_args.encode_fps = float(preset.frame_rate)
    next_args.quality = preset.quality
    next_args.screencast_quality = preset.quality
    next_args.every_nth_frame = preset.every_nth_frame
    next_args.relay_mode = preset.relay_mode
    next_args.chromium_arg = list(preset.chromium_args)
    next_args.disable_default_chromium_args = not preset.include_default_chromium_args
    next_args.vt_preset = preset.vt_preset
    next_args.encoder = "h264_videotoolbox" if sys.platform == "darwin" else "libx264"
    next_args.ffmpeg_mode = "service"
    next_args.profile = "high"
    next_args.source_mode = "overlay"
    next_args.video_bitrate_k = preset.bitrate_k
    next_args.ffmpeg_input_mode = preset.ffmpeg_input_mode
    next_args.stdin_flush_mode = preset.stdin_flush_mode
    next_args.muxrate_policy = preset.muxrate_policy
    return next_args


async def run_service_config_compare(args: argparse.Namespace) -> dict[str, Any]:
    overlay_results: list[dict[str, Any]] = []
    relay_results: list[dict[str, Any]] = []
    strategies = args.strategy or ["naive_repeat_last"]
    for preset_name in ["legacy", "current"]:
        preset_args = apply_service_config_preset(args, preset_name)
        for strategy in strategies:
            runner = OverlayCaptureRunner(preset_args, strategy)
            runner.start()
            await asyncio.sleep(preset_args.seconds)
            await runner.stop()
            result = runner.result()
            result["relay_mode"] = preset_args.relay_mode
            overlay_results.append(result)
            await asyncio.sleep(0.5)

        relay_args = argparse.Namespace(**vars(preset_args))
        relay_args.source_mode = "synthetic_sparse"
        relay_runner = RelayBroadcastRunner(relay_args)
        relay_runner.start()
        await asyncio.sleep(relay_args.prime_seconds)
        client_tasks = [
            asyncio.create_task(relay_sink_client(relay_runner.stream_url, relay_args.seconds, f"client{i + 1}"))
            for i in range(relay_args.clients)
        ]
        try:
            clients = await asyncio.gather(*client_tasks)
        finally:
            await relay_runner.stop()
        relay_results.append(relay_runner.result(clients))
        await asyncio.sleep(0.5)

    return {
        "benchmark_mode": "service_config_compare",
        "overlay_runs": overlay_results,
        "relay_runs": relay_results,
        "overlay_table": render_service_config_overlay_table(overlay_results),
        "relay_table": render_service_config_relay_table(relay_results),
    }


async def run_relay_broadcast_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    runner = RelayBroadcastRunner(args)
    runner.start()
    await asyncio.sleep(args.prime_seconds)
    client_tasks = [
        asyncio.create_task(relay_sink_client(runner.stream_url, args.seconds, f"client{i + 1}"))
        for i in range(args.clients)
    ]
    try:
        clients = await asyncio.gather(*client_tasks)
    finally:
        await runner.stop()
    return runner.result(clients)


async def run_webrtc_capture_benchmark(args: argparse.Namespace) -> dict[str, Any]:
    results: list[dict[str, Any]] = []
    for scenario in args.webrtc_scenario or WEBRTC_SCENARIOS:
        runner = WebRTCCaptureRunner(args, scenario)
        result = await runner.run()
        results.append(result)
        await asyncio.sleep(0.5)
    return {
        "benchmark_mode": "webrtc_capture_benchmark",
        "runs": results,
        "ranked_table": render_webrtc_table(results),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=["overlay_capture_benchmark", "relay_broadcast_benchmark", "webrtc_capture_benchmark", "service_config_compare"],
        default="overlay_capture_benchmark",
    )
    parser.add_argument("--overlay-url", default=DEFAULT_OVERLAY_URL)
    parser.add_argument("--profile", choices=sorted(PROFILES.keys()), default="low")
    parser.add_argument("--service-config-preset", choices=["custom", "legacy", "current"], default="custom")
    parser.add_argument("--seconds", type=float, default=12.0)
    parser.add_argument("--prime-seconds", type=float, default=1.0)
    parser.add_argument("--clients", type=int, default=2)
    parser.add_argument("--stream-port", type=int)
    parser.add_argument("--encoder", choices=["auto", "libx264", "h264_videotoolbox"], default="libx264")
    parser.add_argument("--ffmpeg-mode", choices=["service", "service_low_latency", "tuned"], default="tuned")
    parser.add_argument("--source-mode", choices=["overlay", "synthetic_sparse"], default="overlay")
    parser.add_argument("--strategy", action="append", choices=[
        "naive_repeat_last",
        "adaptive_repeat_last",
        "frame_interpolation_stub",
        "burst_smoothing",
        "speed_control_repeat",
        "speed_control_burst_smoothing",
        "speed_control_interpolation",
    ])
    parser.add_argument("--encode-fps", type=float, default=8.0)
    parser.add_argument("--min-encode-fps", type=float, default=2.0)
    parser.add_argument("--max-encode-fps", type=float, default=30.0)
    parser.add_argument("--repeat-last-after-idle-ms", type=int, default=300)
    parser.add_argument("--adaptive-step-up", type=float, default=1.5)
    parser.add_argument("--adaptive-step-down", type=float, default=0.75)
    parser.add_argument("--stdin-backoff-ms", type=float, default=3.0)
    parser.add_argument("--target-ffmpeg-speed", type=float, default=1.0)
    parser.add_argument("--speed-ema-alpha", type=float, default=0.22)
    parser.add_argument("--speed-control-kp", type=float, default=0.35)
    parser.add_argument("--max-rate-step-ratio", type=float, default=0.15)
    parser.add_argument("--stdin-control-gain", type=float, default=0.08)
    parser.add_argument("--progress-timeout-ms", type=float, default=2200.0)
    parser.add_argument("--search-growth-ratio", type=float, default=0.03)
    parser.add_argument("--zero-speed-persist-samples", type=int, default=3)
    parser.add_argument("--burst-smoothing-window", type=int, default=4)
    parser.add_argument("--synthetic-source-fps", type=float, default=1.0)
    parser.add_argument("--viewport-width", type=int)
    parser.add_argument("--viewport-height", type=int)
    parser.add_argument("--capture-width", type=int)
    parser.add_argument("--capture-height", type=int)
    parser.add_argument("--stream-fps", type=int)
    parser.add_argument("--quality", type=int)
    parser.add_argument("--video-bitrate-k", type=int)
    parser.add_argument("--muxrate-policy", choices=["auto", "fixed_4000k", "bitrate", "bitrate_x1_5", "none"], default="auto")
    parser.add_argument("--gop-multiplier", type=float)
    parser.add_argument("--gop-frames", type=int)
    parser.add_argument("--ffmpeg-input-mode", choices=["image2pipe", "mjpeg"], default="image2pipe")
    parser.add_argument("--decode-mode", choices=["inline", "worker"], default="inline")
    parser.add_argument("--stdin-flush-mode", choices=["every", "batched", "none"], default="every")
    parser.add_argument("--stdin-flush-every", type=int, default=5)
    parser.add_argument("--every-nth-frame", type=int, default=1)
    parser.add_argument("--screencast-quality", type=int, default=24)
    parser.add_argument(
        "--gpu-mode",
        choices=["default", "disable-gpu", "swiftshader", "webgpu"],
        default="default",
    )
    parser.add_argument("--chromium-arg", action="append", default=[])
    parser.add_argument("--disable-default-chromium-args", action="store_true")
    parser.add_argument("--relay-mode", choices=["shared-read", "fanout"], default="fanout")
    parser.add_argument("--fanout-queue-chunks", type=int, default=32)
    parser.add_argument("--vt-preset", choices=["auto", "legacy", "current"], default="auto")
    parser.add_argument("--webrtc-capture-fps", type=float, default=15.0)
    parser.add_argument("--webrtc-scenario", action="append", choices=WEBRTC_SCENARIOS)
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    if args.mode == "overlay_capture_benchmark":
        result = await run_overlay_capture_benchmark(args)
    elif args.mode == "service_config_compare":
        result = await run_service_config_compare(args)
    elif args.mode == "webrtc_capture_benchmark":
        result = await run_webrtc_capture_benchmark(args)
    else:
        result = await run_relay_broadcast_benchmark(args)
    print(json.dumps(result, indent=2, sort_keys=True))
    if isinstance(result, dict) and "ranked_table" in result:
        print(result["ranked_table"])
    if isinstance(result, dict) and "overlay_table" in result:
        print(result["overlay_table"])
    if isinstance(result, dict) and "relay_table" in result:
        print(result["relay_table"])
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
