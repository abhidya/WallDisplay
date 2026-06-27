from fastapi import FastAPI
from fastapi.testclient import TestClient

import web.backend.routers.structured_lighting_router as structured_lighting_router


class FakeStructuredLightingService:
    def render_step_image(self, session_id, step_index):
        if session_id == "session-1" and step_index == 0:
            return b"png"
        return None


def make_client(monkeypatch):
    app = FastAPI()
    app.include_router(structured_lighting_router.router)
    monkeypatch.setattr(
        structured_lighting_router,
        "get_structured_lighting_service",
        lambda: FakeStructuredLightingService(),
    )
    return TestClient(app)


def test_present_step_page_is_clean_projector_output(monkeypatch):
    client = make_client(monkeypatch)

    response = client.get(
        "/api/structured-lighting/sessions/session-1/steps/0/present?projector_id=proj-hdmi"
    )

    assert response.status_code == 200
    assert 'src="/api/structured-lighting/sessions/session-1/steps/0/image"' in response.text
    assert "/api/renderer/heartbeat/proj-hdmi" in response.text
    assert "Reference White" not in response.text
    assert "hud" not in response.text.lower()
