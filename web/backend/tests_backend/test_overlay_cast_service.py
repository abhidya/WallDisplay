import asyncio
import time

import pytest

from web.backend.services.overlay_cast_service import OverlayCastService, OverlayCastSession


@pytest.mark.anyio
async def test_start_cast_returns_after_relay_ready(monkeypatch):
    service = OverlayCastService()

    async def fake_run_session(self, session, **kwargs):
        session.status = "preparing"
        session.ready_event.set()
        await asyncio.sleep(0.05)
        session.status = "running"
        session.discovery_session_id = "disc-123"
        await session.stop_event.wait()

    monkeypatch.setattr(OverlayCastService, "_run_session", fake_run_session)
    monkeypatch.setattr(OverlayCastService, "_reserve_free_port", lambda self: 51234)
    monkeypatch.setattr(OverlayCastService, "_get_local_ip", lambda self: "127.0.0.1")

    started = time.monotonic()
    session = await service.start_cast(
        device_id="dlna-test-device",
        config_id=4,
        overlay_base_url="http://localhost:3000",
    )
    elapsed = time.monotonic() - started

    assert elapsed < 0.03
    assert session["status"] == "preparing"
    assert session["current_step"] == "queued"
    assert "capture=dlna" in session["overlay_url"]

    await service.stop_cast(session["session_id"])


def test_latest_frame_overwrites_older_frame():
    service = OverlayCastService()
    session = OverlayCastSession(
        session_id="session-1",
        device_id="dlna-test-device",
        config_id=1,
        overlay_url="http://localhost/overlay",
        relay_url="http://localhost/live.mp4",
        stream_port=5000,
    )
    session.latest_frame = b"frame-1"
    session.latest_frame = b"frame-2"

    assert session.latest_frame == b"frame-2"


def test_build_ffmpeg_command_prefers_videotoolbox_on_macos(monkeypatch):
    service = OverlayCastService()

    monkeypatch.setattr("web.backend.services.overlay_cast_service.sys.platform", "darwin")

    encoder, command = service._build_ffmpeg_command(frame_rate=15, capture_width=960, capture_height=540)

    assert encoder == "h264_videotoolbox"
    assert "-realtime" in command
    assert "-prio_speed" in command
    assert "-allow_sw" in command
    assert "2200k" in command
    assert "500000" in command


def test_build_ffmpeg_command_uses_low_latency_x264_elsewhere(monkeypatch):
    service = OverlayCastService()

    monkeypatch.setattr("web.backend.services.overlay_cast_service.sys.platform", "linux")

    encoder, command = service._build_ffmpeg_command(frame_rate=8, capture_width=640, capture_height=360)

    assert encoder == "libx264"
    assert "-tune" in command
    assert "zerolatency" in command
    assert "-bf" in command
    assert "900k" in command
