import io
import time

from web.backend.core.renderer_service.sender.hdmi import HDMISender


class FakeProcess:
    def __init__(self):
        self.returncode = None
        self.stderr = io.BytesIO(b"")
        self.terminated = False
        self.killed = False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        self.returncode = 0

    def kill(self):
        self.killed = True
        self.returncode = -9


def display(index=1):
    return {
        "id": f"hdmi_display_{index}",
        "index": index,
        "name": f"Display {index}",
        "x": 1920 * index,
        "y": 0,
        "width": 1280,
        "height": 720,
        "is_primary": index == 0,
        "attached": True,
        "device_name": f"DISPLAY{index}",
    }


def test_discover_displays_falls_back_when_detectors_are_unavailable(monkeypatch):
    monkeypatch.setattr("web.backend.core.renderer_service.sender.hdmi.platform.system", lambda: "Windows")
    monkeypatch.setattr(HDMISender, "_discover_windows", staticmethod(lambda: []))
    monkeypatch.setattr(HDMISender, "_discover_with_screeninfo", staticmethod(lambda: []))

    displays = HDMISender.discover_displays()

    assert displays == [
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
            "device_name": None,
        }
    ]


def test_send_content_launches_browser_on_target_display_and_marks_stale(monkeypatch):
    fake_process = FakeProcess()
    launched = []
    monkeypatch.setattr(HDMISender, "discover_displays", classmethod(lambda cls: [display(1)]))
    monkeypatch.setattr("web.backend.core.renderer_service.sender.hdmi.time.sleep", lambda _seconds: None)
    monkeypatch.setattr(
        "web.backend.core.renderer_service.sender.hdmi.subprocess.Popen",
        lambda cmd, **kwargs: launched.append(cmd) or fake_process,
    )

    sender = HDMISender({"heartbeat_timeout_seconds": 0.01, "isolated_profile": False})
    monkeypatch.setattr(sender, "_get_browser_command", lambda: r"C:\Chrome\chrome.exe")

    assert sender.connect("1") is True
    assert sender.send_content(
        "http://localhost:8000/api/structured-lighting/sessions/session-1/steps/0/present?projector_id=proj"
    ) is True

    assert launched
    assert "--window-position=1920,0" in launched[0]
    assert "--window-size=1280,720" in launched[0]
    assert sender.get_status()["projection_state"] == "projecting"

    sender.started_at = time.time() - 1
    stale_status = sender.get_status()
    assert stale_status["connection_state"] == "unresponsive"
    assert stale_status["projection_state"] == "stale"

    sender.record_heartbeat()
    assert sender.get_status()["projection_state"] == "projecting"

    assert sender.disconnect() is True
    assert fake_process.terminated is True


def test_missing_display_marks_sender_detached(monkeypatch):
    monkeypatch.setattr(HDMISender, "discover_displays", classmethod(lambda cls: [display(0)]))

    sender = HDMISender({})

    assert sender.connect("missing") is False
    status = sender.get_status()
    assert status["connection_state"] == "detached"
    assert status["projection_state"] == "stale"
    assert "Display target not found" in status["last_error"]
