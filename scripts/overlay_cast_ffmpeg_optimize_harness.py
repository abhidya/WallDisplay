#!/usr/bin/env python3
"""FFmpeg optimization harness for macOS AVFoundation overlay capture.

This script treats FFmpeg as a black box and benchmarks a matrix of capture and
encode settings until it finds a configuration that clears realtime.
"""

from __future__ import annotations

import argparse
import dataclasses
import itertools
import os
import queue
import re
import shlex
import shutil
import subprocess
import sys
import threading
import time
from typing import Iterable, Optional


DISPLAY_DEVICE_RE = re.compile(r"\[(\d+)\]\s+(Capture screen .+)")
PROGRESS_RE = re.compile(r"^([a-zA-Z0-9_]+)=(.+)$")
SPEED_VALUE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)x")
FPS_VALUE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)")
BITRATE_VALUE_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)kbits/s")


@dataclasses.dataclass(frozen=True)
class EncoderVariant:
    name: str
    encoder: str
    videotoolbox_realtime: bool = False
    videotoolbox_prio_speed: bool = False
    videotoolbox_realtime_priority: bool = False


@dataclasses.dataclass(frozen=True)
class HarnessConfig:
    encoder_variant: EncoderVariant
    width: int
    height: int
    frame_rate: int
    bitrate: str
    gop: int
    use_scale_filter: bool

    @property
    def resolution(self) -> str:
        return f"{self.width}x{self.height}"

    @property
    def config_id(self) -> str:
        scale_tag = "scale" if self.use_scale_filter else "native"
        return (
            f"{self.encoder_variant.name}|{self.resolution}|{self.frame_rate}fps|"
            f"{self.bitrate}|gop{self.gop}|{scale_tag}"
        )


@dataclasses.dataclass
class RunResult:
    config: HarnessConfig
    success: bool
    status: str
    display_index: int
    display_name: str
    ffmpeg_command: list[str]
    speed_avg: Optional[float]
    speed_max: Optional[float]
    fps_avg: Optional[float]
    bitrate_avg_kbps: Optional[float]
    frame_count_max: Optional[int]
    failure_reason: Optional[str] = None
    warnings: list[str] = dataclasses.field(default_factory=list)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=10, help="Seconds per FFmpeg run.")
    parser.add_argument("--display-index", type=int, help="Override AVFoundation display device index.")
    parser.add_argument("--limit", type=int, help="Only run the first N generated configs.")
    parser.add_argument(
        "--output-format",
        choices=["mpegts", "null"],
        default="mpegts",
        help="FFmpeg sink used for benchmarking.",
    )
    parser.add_argument(
        "--include-realtime-priority",
        action="store_true",
        help="Include videotoolbox variants with realtime_priority=1. Some FFmpeg builds do not support it.",
    )
    return parser.parse_args()


def ensure_ffmpeg() -> str:
    ffmpeg = shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("ffmpeg is not installed or not on PATH.")
    return ffmpeg


def detect_display_device(ffmpeg_bin: str) -> tuple[int, str]:
    proc = subprocess.run(
        [ffmpeg_bin, "-f", "avfoundation", "-list_devices", "true", "-i", ""],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    output = f"{proc.stdout}\n{proc.stderr}"
    matches = []
    for line in output.splitlines():
        match = DISPLAY_DEVICE_RE.search(line)
        if match:
            matches.append(match.groups())
    if not matches:
        raise RuntimeError("Could not find an AVFoundation display capture device.")
    index_text, name = matches[0]
    return int(index_text), name.strip()


def generate_configs(include_realtime_priority: bool) -> Iterable[HarnessConfig]:
    encoder_variants = [
        EncoderVariant(
            name="vt_rt_speed",
            encoder="h264_videotoolbox",
            videotoolbox_realtime=True,
            videotoolbox_prio_speed=True,
        ),
        EncoderVariant(
            name="vt_realtime",
            encoder="h264_videotoolbox",
            videotoolbox_realtime=True,
        ),
        EncoderVariant(name="x264_ultrafast", encoder="libx264"),
    ]
    if include_realtime_priority:
        encoder_variants.insert(
            0,
            EncoderVariant(
                name="vt_rt_speed_priority",
                encoder="h264_videotoolbox",
                videotoolbox_realtime=True,
                videotoolbox_prio_speed=True,
                videotoolbox_realtime_priority=True,
            ),
        )
    for variant, (width, height), frame_rate, bitrate, gop_multiplier, use_scale_filter in itertools.product(
        encoder_variants,
        [(1920, 1080), (1280, 720), (854, 480)],
        [24, 20, 15, 12],
        ["3000k", "2000k", "1200k"],
        [1, 2],
        [False, True],
    ):
        yield HarnessConfig(
            encoder_variant=variant,
            width=width,
            height=height,
            frame_rate=frame_rate,
            bitrate=bitrate,
            gop=frame_rate * gop_multiplier,
            use_scale_filter=use_scale_filter,
        )


def build_ffmpeg_command(
    ffmpeg_bin: str,
    config: HarnessConfig,
    display_index: int,
    duration: int,
    output_format: str,
) -> list[str]:
    cmd = [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "info",
        "-nostdin",
        "-stats_period",
        "0.5",
        "-progress",
        "pipe:2",
        "-f",
        "avfoundation",
        "-capture_cursor",
        "1",
        "-pixel_format",
        "nv12",
        "-framerate",
        str(config.frame_rate),
        "-i",
        f"{display_index}:none",
        "-t",
        str(duration),
        "-an",
    ]
    if config.use_scale_filter:
        cmd.extend(["-vf", f"scale={config.width}:{config.height}:flags=fast_bilinear"])

    cmd.extend(["-c:v", config.encoder_variant.encoder])
    if config.encoder_variant.encoder == "h264_videotoolbox":
        if config.encoder_variant.videotoolbox_realtime:
            cmd.extend(["-realtime", "1"])
        if config.encoder_variant.videotoolbox_prio_speed:
            cmd.extend(["-prio_speed", "1"])
        if config.encoder_variant.videotoolbox_realtime_priority:
            cmd.extend(["-realtime_priority", "1"])
        cmd.extend(["-allow_sw", "1"])
    else:
        cmd.extend(["-preset", "ultrafast", "-tune", "zerolatency", "-threads", "0"])

    cmd.extend(
        [
            "-profile:v",
            "baseline",
            "-b:v",
            config.bitrate,
            "-maxrate",
            config.bitrate,
            "-bufsize",
            str(int(config.bitrate.rstrip("k")) * 2) + "k",
            "-pix_fmt",
            "yuv420p",
            "-g",
            str(config.gop),
            "-keyint_min",
            str(config.gop),
            "-bf",
            "0",
            "-vsync",
            "1",
        ]
    )

    if output_format == "mpegts":
        cmd.extend(["-f", "mpegts", "pipe:1"])
    else:
        cmd.extend(["-f", "null", "-"])
    return cmd


def parse_progress_value(raw_value: str, parser_re: re.Pattern[str]) -> Optional[float]:
    match = parser_re.search(raw_value)
    return float(match.group(1)) if match else None


def run_config(
    ffmpeg_bin: str,
    config: HarnessConfig,
    display_index: int,
    display_name: str,
    duration: int,
    output_format: str,
) -> RunResult:
    command = build_ffmpeg_command(ffmpeg_bin, config, display_index, duration, output_format)
    proc = subprocess.Popen(
        command,
        stdout=subprocess.DEVNULL if output_format == "mpegts" else subprocess.DEVNULL,
        stderr=subprocess.PIPE,
        stdin=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )
    speed_samples: list[float] = []
    fps_samples: list[float] = []
    bitrate_samples: list[float] = []
    warnings: list[str] = []
    frame_count_max: Optional[int] = None
    failure_reason: Optional[str] = None
    stderr_queue: queue.Queue[Optional[str]] = queue.Queue()

    def _read_stderr() -> None:
        assert proc.stderr is not None
        for raw_line in proc.stderr:
            stderr_queue.put(raw_line)
        stderr_queue.put(None)

    stderr_thread = threading.Thread(target=_read_stderr, daemon=True)
    stderr_thread.start()

    try:
        deadline = time.monotonic() + duration + 8
        stderr_closed = False
        while True:
            if time.monotonic() > deadline:
                failure_reason = failure_reason or "Timed out waiting for FFmpeg run to complete"
                proc.kill()
                break
            try:
                raw_line = stderr_queue.get(timeout=0.25)
            except queue.Empty:
                if proc.poll() is not None and stderr_closed:
                    break
                continue
            if raw_line is None:
                stderr_closed = True
                if proc.poll() is not None:
                    break
                continue
            line = raw_line.strip()
            if not line:
                continue

            match = PROGRESS_RE.match(line)
            if match:
                key, value = match.groups()
                if key == "speed":
                    parsed = parse_progress_value(value, SPEED_VALUE_RE)
                    if parsed is not None:
                        speed_samples.append(parsed)
                elif key == "fps":
                    parsed = parse_progress_value(value, FPS_VALUE_RE)
                    if parsed is not None:
                        fps_samples.append(parsed)
                elif key == "bitrate":
                    parsed = parse_progress_value(value, BITRATE_VALUE_RE)
                    if parsed is not None:
                        bitrate_samples.append(parsed)
                elif key == "frame":
                    try:
                        frame_count_max = max(frame_count_max or 0, int(value))
                    except ValueError:
                        pass
                continue

            lowered = line.lower()
            if "error" in lowered or "invalid" in lowered or "unsupported" in lowered:
                warnings.append(line)
                if failure_reason is None:
                    failure_reason = line
            elif "warning" in lowered:
                warnings.append(line)
    finally:
        try:
            proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)

    speed_avg = sum(speed_samples) / len(speed_samples) if speed_samples else None
    speed_max = max(speed_samples) if speed_samples else None
    fps_avg = sum(fps_samples) / len(fps_samples) if fps_samples else None
    bitrate_avg = sum(bitrate_samples) / len(bitrate_samples) if bitrate_samples else None

    if proc.returncode not in (0, None):
        failure_reason = failure_reason or f"ffmpeg exited with code {proc.returncode}"

    success = failure_reason is None and speed_avg is not None and speed_avg >= 1.0
    status = "PASS" if success else "FAIL"
    if speed_avg is None and failure_reason is None:
        failure_reason = "No speed samples parsed from FFmpeg progress output"
    elif speed_avg is not None and speed_avg < 1.0 and failure_reason is None:
        failure_reason = f"speed_avg={speed_avg:.2f}x"

    return RunResult(
        config=config,
        success=success,
        status=status,
        display_index=display_index,
        display_name=display_name,
        ffmpeg_command=command,
        speed_avg=speed_avg,
        speed_max=speed_max,
        fps_avg=fps_avg,
        bitrate_avg_kbps=bitrate_avg,
        frame_count_max=frame_count_max,
        failure_reason=failure_reason,
        warnings=warnings,
    )


def choose_golden_config(results: list[RunResult]) -> Optional[RunResult]:
    passing = [result for result in results if result.success]
    if not passing:
        return None
    return max(
        passing,
        key=lambda result: (
            result.config.width * result.config.height,
            result.config.frame_rate,
            result.speed_avg or 0.0,
        ),
    )


def render_markdown(results: list[RunResult], golden: Optional[RunResult]) -> str:
    lines = []
    lines.append("| status | encoder | resolution | fps | bitrate | gop | scale | speed_avg | speed_max | fps_avg | bitrate_avg_kbps | frames | notes |")
    lines.append("|---|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---|")
    for result in results:
        notes = result.failure_reason or ""
        row = [
            f"**{result.status}**" if golden and result.config.config_id == golden.config.config_id else result.status,
            result.config.encoder_variant.name,
            result.config.resolution,
            str(result.config.frame_rate),
            result.config.bitrate,
            str(result.config.gop),
            "yes" if result.config.use_scale_filter else "no",
            f"{result.speed_avg:.2f}" if result.speed_avg is not None else "n/a",
            f"{result.speed_max:.2f}" if result.speed_max is not None else "n/a",
            f"{result.fps_avg:.2f}" if result.fps_avg is not None else "n/a",
            f"{result.bitrate_avg_kbps:.1f}" if result.bitrate_avg_kbps is not None else "n/a",
            str(result.frame_count_max or 0),
            notes.replace("|", "/"),
        ]
        lines.append("| " + " | ".join(row) + " |")
    if golden:
        lines.append("")
        lines.append(
            f"Golden config: `{golden.config.config_id}` on display `{golden.display_name}` "
            f"(speed_avg={golden.speed_avg:.2f}x, fps_avg={golden.fps_avg or 0.0:.2f})"
        )
    else:
        lines.append("")
        lines.append("Golden config: none, no tested configuration cleared realtime.")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    ffmpeg_bin = ensure_ffmpeg()
    if args.display_index is None:
        display_index, display_name = detect_display_device(ffmpeg_bin)
    else:
        detected_index, detected_name = detect_display_device(ffmpeg_bin)
        display_index = args.display_index
        display_name = detected_name if detected_index == args.display_index else f"Capture screen {args.display_index}"

    configs = list(generate_configs(args.include_realtime_priority))
    if args.limit:
        configs = configs[: args.limit]

    print(f"# OverlayCast FFmpeg Optimization Harness")
    print(f"- Host: `{os.uname().nodename}`")
    print(f"- Display device: `{display_index}` (`{display_name}`)")
    print(f"- Duration per run: `{args.duration}s`")
    print(f"- Output format: `{args.output_format}`")
    print(f"- Total configurations: `{len(configs)}`")
    print("")

    results: list[RunResult] = []
    start = time.monotonic()
    for index, config in enumerate(configs, start=1):
        print(f"Running {index}/{len(configs)}: {config.config_id}", file=sys.stderr)
        result = run_config(ffmpeg_bin, config, display_index, display_name, args.duration, args.output_format)
        results.append(result)

    golden = choose_golden_config(results)
    print(render_markdown(results, golden))
    print("")
    print(f"Completed in {time.monotonic() - start:.1f}s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
