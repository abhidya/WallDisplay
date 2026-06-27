from fastapi import FastAPI
from fastapi.testclient import TestClient

import web.backend.routers.renderer_router as renderer_router


class FakeRendererService:
    def __init__(self):
        self.projector_power_states = {}
        self.projector_target = "0"
        self.status = None
        self.heartbeat_count = 0

    def list_hdmi_displays(self):
        return [
            {
                "id": "hdmi_display_0",
                "index": 0,
                "name": "Primary display",
                "x": 0,
                "y": 0,
                "width": 1920,
                "height": 1080,
                "is_primary": True,
                "attached": True,
                "device_name": "DISPLAY0",
            }
        ]

    def get_projector_config(self, projector_id):
        return {
            "id": projector_id,
            "name": "HDMI Projector",
            "sender": "hdmi",
            "target_name": self.projector_target,
        }

    def get_renderer_status(self, projector_id):
        return self.status

    def set_projector_target(self, projector_id, target_name):
        if target_name != "hdmi_display_0":
            return False
        self.projector_target = target_name
        return True

    def start_projector_mode(self, projector_id, mode, options=None):
        self.status = {
            "projector_id": projector_id,
            "sender_type": "hdmi",
            "target_name": self.projector_target,
            "content_mode": mode,
            "options": options or {},
            "status": "projecting",
            "sender_status": {
                "type": "hdmi",
                "connection_state": "attached",
                "projection_state": "projecting",
                "power_state": self.projector_power_states.get(projector_id, "unknown"),
            },
        }
        return True

    def identify_projector(self, projector_id):
        return self.start_projector_mode(projector_id, "identify", {})

    def set_projector_power_state(self, projector_id, power_state):
        if power_state not in {"unknown", "manual_on", "manual_off"}:
            return False
        self.projector_power_states[projector_id] = power_state
        if self.status:
            self.status["sender_status"]["power_state"] = power_state
        return True

    def record_projector_heartbeat(self, projector_id):
        self.heartbeat_count += 1
        return True


def make_client(monkeypatch, fake_service):
    app = FastAPI()
    app.include_router(renderer_router.router, prefix="/api")
    monkeypatch.setattr(renderer_router, "renderer_service", fake_service)
    return TestClient(app)


def test_hdmi_displays_and_target_routes(monkeypatch):
    fake_service = FakeRendererService()
    client = make_client(monkeypatch, fake_service)

    response = client.get("/api/renderer/hdmi/displays")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["displays"][0]["id"] == "hdmi_display_0"

    target_response = client.post(
        "/api/renderer/projectors/proj-hdmi/target",
        json={"target_name": "hdmi_display_0"},
    )
    assert target_response.status_code == 200
    assert fake_service.projector_target == "hdmi_display_0"


def test_hdmi_mode_identify_power_and_heartbeat_routes(monkeypatch):
    fake_service = FakeRendererService()
    client = make_client(monkeypatch, fake_service)

    mode_response = client.post(
        "/api/renderer/projectors/proj-hdmi/mode",
        json={"mode": "blank", "options": {"background_color": "black"}},
    )
    assert mode_response.status_code == 200
    assert mode_response.json()["data"]["content_mode"] == "blank"

    identify_response = client.post("/api/renderer/projectors/proj-hdmi/identify")
    assert identify_response.status_code == 200
    assert identify_response.json()["data"]["content_mode"] == "identify"

    power_response = client.post(
        "/api/renderer/projectors/proj-hdmi/power-state",
        json={"power_state": "manual_on"},
    )
    assert power_response.status_code == 200
    assert power_response.json()["data"]["sender_status"]["power_state"] == "manual_on"

    heartbeat_response = client.post("/api/renderer/heartbeat/proj-hdmi")
    assert heartbeat_response.status_code == 200
    assert fake_service.heartbeat_count == 1
