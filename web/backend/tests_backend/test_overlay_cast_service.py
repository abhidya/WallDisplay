import asyncio
import queue
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


def test_enqueue_frame_drops_oldest_when_queue_is_full():
    service = OverlayCastService()
    session = OverlayCastSession(
        session_id="session-1",
        device_id="dlna-test-device",
        config_id=1,
        overlay_url="http://localhost/overlay",
        relay_url="http://localhost/live.ts",
        stream_port=5000,
    )
    session.frame_queue = queue.Queue(maxsize=1)

    service._enqueue_frame(session, b"frame-1")
    service._enqueue_frame(session, b"frame-2")

    assert session.frame_queue.qsize() == 1
    assert session.frame_queue.get_nowait() == b"frame-2"
