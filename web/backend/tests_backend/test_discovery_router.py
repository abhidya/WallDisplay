import asyncio
from types import SimpleNamespace

from web.backend.api import discovery_router


def test_cast_content_response_uses_unified_casting_session_fields(monkeypatch):
    session = SimpleNamespace(
        id="session-1",
        device=SimpleNamespace(id="proj-hdmi-local"),
    )

    class _Manager:
        async def cast_content(self, **kwargs):
            assert kwargs["device_id"] == "proj-hdmi-local"
            assert kwargs["content_url"] == "http://127.0.0.1:8088/backend-static/blank.html"
            assert kwargs["content_type"] == "text/html"
            assert kwargs["metadata"] == {"content_mode": "blank"}
            return session

    monkeypatch.setattr(discovery_router, "_get_discovery_manager", lambda: _Manager())

    result = asyncio.run(
        discovery_router.cast_content(
            device_id="proj-hdmi-local",
            content_url="http://127.0.0.1:8088/backend-static/blank.html",
            content_type="text/html",
            metadata={"content_mode": "blank"},
        )
    )

    assert result == {
        "session_id": "session-1",
        "device_id": "proj-hdmi-local",
        "status": "started",
    }
