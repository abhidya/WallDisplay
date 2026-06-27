from web.backend.core.renderer_service.output_session import ProjectorOutputSession


class FakeSender:
    VALID_POWER_STATES = {"unknown", "manual_on", "manual_off"}

    def __init__(self):
        self.connected_to = None
        self.content_url = None
        self.disconnected = False
        self.heartbeat_count = 0
        self.power_state = "unknown"

    def connect(self, target_name):
        self.connected_to = target_name
        return True

    def send_content(self, content_url):
        self.content_url = content_url
        return True

    def disconnect(self):
        self.disconnected = True
        return True

    def record_heartbeat(self):
        self.heartbeat_count += 1

    def set_power_state(self, power_state):
        self.power_state = power_state

    def get_status(self):
        return {
            "type": "hdmi",
            "target": self.connected_to,
            "connection_state": "attached",
            "projection_state": "projecting",
            "power_state": self.power_state,
            "process_running": True,
            "content_url": self.content_url,
            "last_error": None,
            "last_heartbeat_at": None,
        }


def test_projector_output_session_owns_hdmi_mode_url_status_and_heartbeat():
    created = []

    def make_sender():
        sender = FakeSender()
        created.append(sender)
        return sender

    session = ProjectorOutputSession(
        "proj-hdmi",
        {"sender": "hdmi", "target_name": "DISPLAY1"},
        sender_factory=make_sender,
        server_base_url="http://wall.local/",
    )

    assert session.start_mode("overlay", {"config_id": 7}) is True

    sender = created[0]
    assert sender.connected_to == "DISPLAY1"
    assert sender.content_url == (
        "http://wall.local/backend-static/overlay_window.html?"
        "projector_id=proj-hdmi&mode=overlay&config_id=7&controls=hidden"
    )

    assert session.record_heartbeat() is True
    assert sender.heartbeat_count == 1

    session.set_power_state("manual_on")
    status = session.status()
    assert status["projector_id"] == "proj-hdmi"
    assert status["sender_type"] == "hdmi"
    assert status["content_mode"] == "overlay"
    assert status["status"] == "projecting"
    assert status["sender_status"]["power_state"] == "manual_on"

    assert session.stop() is True
    assert sender.disconnected is True
