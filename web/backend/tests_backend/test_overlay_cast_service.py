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
