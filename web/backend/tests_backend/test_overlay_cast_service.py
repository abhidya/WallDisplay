import asyncio
import time
from types import SimpleNamespace

import pytest

from web.backend.services.overlay_cast_service import FanoutRelayState, OverlayCastService, OverlayCastSession


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
    monkeypatch.setattr(OverlayCastService, "_get_local_ip", lambda self, device_id=None: "127.0.0.1")

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


def test_fanout_relay_state_drops_oldest_chunk_instead_of_unregistering_client():
    relay_state = FanoutRelayState()
    _, client_queue = relay_state.register_client()

    for index in range(client_queue.maxsize):
        relay_state.publish(f"frame-{index}".encode())

    relay_state.publish(b"latest-frame")

    drained = []
    while not client_queue.empty():
        drained.append(client_queue.get_nowait())

    assert relay_state.active_client_count == 1
    assert len(drained) == client_queue.maxsize
    assert drained[0] == b"frame-1"
    assert drained[-1] == b"latest-frame"


def test_get_local_ip_prefers_same_subnet_as_device(monkeypatch):
    service = OverlayCastService()

    monkeypatch.delenv("STREAMING_SERVE_IP", raising=False)
    monkeypatch.delenv("NANODLNA_DISCOVERY_INTERFACE_IP", raising=False)
    monkeypatch.delenv("SERVE_IP", raising=False)
    monkeypatch.setattr(
        "web.backend.services.overlay_cast_service.get_local_ipv4_addresses",
        lambda: {"10.0.0.63", "192.168.1.50"},
    )
    monkeypatch.setattr(
        service.discovery_manager,
        "get_device_by_id",
        lambda device_id: SimpleNamespace(hostname="10.0.0.154"),
    )

    assert service._get_local_ip("dlna-test-device") == "10.0.0.63"


def test_frame_writer_ignores_closed_pipe_after_ffmpeg_exit():
    service = OverlayCastService()
    session = OverlayCastSession(
        session_id="session-1",
        device_id="dlna-test-device",
        config_id=1,
        overlay_url="http://localhost/overlay",
        relay_url="http://localhost/live.mp4",
        stream_port=5000,
    )
    session.latest_frame = b"frame"

    class ClosedPipe:
        def write(self, _data):
            raise ValueError("write to closed file")

        def flush(self):
            return None

    class FakeProc:
        stdin = ClosedPipe()

        @staticmethod
        def poll():
            return 0

    service._pump_latest_frame_to_ffmpeg(session, FakeProc())

    assert session.error is None
    assert not session.stop_event.is_set()
