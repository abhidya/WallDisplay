import io
import json

from web.backend.core.renderer_service.sender.hdmi import HDMISender
from web.backend.core.renderer_service.service import RendererService


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.stderr = io.BytesIO(b"")

    def poll(self):
        return self.returncode

    def terminate(self):
        self.returncode = 0

    def kill(self):
        self.returncode = -9


def write_hdmi_config(tmp_path):
    config = {
        "server_base_url": "http://testserver",
        "senders": {
            "hdmi": {
                "default_display": 0,
                "heartbeat_timeout_seconds": 30,
                "isolated_profile": False,
            }
        },
        "renderers": {},
        "scenes": {},
        "projectors": {
            "proj-hdmi": {
                "name": "HDMI Test Projector",
                "sender": "hdmi",
                "target_name": "0",
                "content_mode": "identify",
                "content_modes": ["identify", "structured_light", "overlay", "blank", "scene"],
            }
        },
    }
    config_path = tmp_path / "renderer_config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    return config_path


def test_renderer_service_starts_structured_light_on_hdmi(monkeypatch, tmp_path):
    target_display = {
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
    monkeypatch.setattr(HDMISender, "discover_displays", classmethod(lambda cls: [target_display]))
    monkeypatch.setattr(HDMISender, "_get_browser_command", lambda self: r"C:\Chrome\chrome.exe")
    monkeypatch.setattr("web.backend.core.renderer_service.sender.hdmi.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "web.backend.core.renderer_service.sender.hdmi.subprocess.Popen",
        lambda cmd, **kwargs: FakeProcess(),
    )

    service = RendererService(config_file=str(write_hdmi_config(tmp_path)))

    assert service.list_hdmi_displays() == [target_display]
    projectors = service.list_projectors()
    assert projectors[0]["id"] == "proj-hdmi"
    assert projectors[0]["runtime_status"]["status"] == "idle"
    assert projectors[0]["runtime_status"]["sender_status"]["connection_state"] == "attached"

    assert service.start_projector("proj-hdmi") is True
    assert service.get_renderer_status("proj-hdmi")["content_mode"] == "identify"
    assert service.stop_renderer("proj-hdmi") is True

    assert service.start_projector_mode(
        "proj-hdmi",
        "structured_light",
        {"pattern_set": "grid", "safe_black_between_frames": True, "frame_duration_ms": 250},
    ) is True

    status = service.get_renderer_status("proj-hdmi")
    assert status["content_mode"] == "structured_light"
    assert status["status"] == "projecting"
    assert status["sender_status"]["connection_state"] == "attached"
    assert status["sender_status"]["projection_state"] == "projecting"
    assert "structured_light.html" in status["sender_status"]["content_url"]
    assert "pattern_set=grid" in status["sender_status"]["content_url"]
    assert "safe_black_between_frames=true" in status["sender_status"]["content_url"]
    assert "frame_duration_ms=250" in status["sender_status"]["content_url"]

    assert service.record_projector_heartbeat("proj-hdmi") is True
    assert service.set_projector_power_state("proj-hdmi", "manual_off") is True
    assert service.get_renderer_status("proj-hdmi")["sender_status"]["power_state"] == "manual_off"

    assert service.stop_renderer("proj-hdmi") is True
    assert service.get_renderer_status("proj-hdmi") is None


def test_renderer_service_persists_hdmi_target_selection(monkeypatch, tmp_path):
    displays = [
        {
            "id": "hdmi_display_1",
            "index": 1,
            "name": "Second display",
            "x": 1920,
            "y": 0,
            "width": 1280,
            "height": 720,
            "is_primary": False,
            "attached": True,
            "device_name": "DISPLAY1",
        }
    ]
    monkeypatch.setattr(HDMISender, "discover_displays", classmethod(lambda cls: displays))
    config_path = write_hdmi_config(tmp_path)
    service = RendererService(config_file=str(config_path))

    assert service.set_projector_target("proj-hdmi", "hdmi_display_1") is True

    saved = json.loads(config_path.read_text(encoding="utf-8"))
    assert saved["projectors"]["proj-hdmi"]["target_name"] == "hdmi_display_1"


def test_renderer_service_rejects_bad_hdmi_power_state(tmp_path):
    service = RendererService(config_file=str(write_hdmi_config(tmp_path)))

    assert service.set_projector_power_state("proj-hdmi", "automatic") is False
