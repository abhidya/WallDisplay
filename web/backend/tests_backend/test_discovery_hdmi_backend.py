import asyncio

from web.backend.discovery.backends.hdmi import HDMIDiscoveryBackend
from web.backend.discovery.base import CastingMethod, DeviceCapability


class _FakeRendererService:
    def __init__(self):
        self.started = []
        self.stopped = []

    def list_projectors(self):
        return [
            {
                "id": "proj-hdmi-local",
                "name": "HDMI Projector",
                "sender": "hdmi",
                "target_name": r"\\.\DISPLAY5",
                "runtime_status": {
                    "sender_status": {
                        "target": r"\\.\DISPLAY5",
                        "connection_state": "attached",
                        "projection_state": "idle",
                        "power_state": "unknown",
                        "display": {
                            "index": 5,
                            "name": r"\\.\DISPLAY5",
                            "x": 1920,
                            "y": 0,
                            "width": 3840,
                            "height": 2160,
                            "is_primary": False,
                        },
                    }
                },
            },
            {
                "id": "proj-network",
                "name": "Network Projector",
                "sender": "dlna",
            },
        ]

    def start_projector_url(self, projector_id, content_url, content_mode="url", options=None):
        self.started.append((projector_id, content_url, content_mode, options or {}))
        return True

    def stop_renderer(self, projector_id):
        self.stopped.append(projector_id)
        return True

    def get_renderer_status(self, projector_id):
        return {"projector_id": projector_id, "status": "projecting"}


def test_hdmi_discovery_backend_discovers_renderer_configured_projectors():
    backend = HDMIDiscoveryBackend(renderer_service=_FakeRendererService())

    devices = asyncio.run(backend.discover_devices())

    assert len(devices) == 1
    device = devices[0]
    assert device.id == "proj-hdmi-local"
    assert device.friendly_name == "HDMI Projector"
    assert device.casting_method == CastingMethod.HDMI
    assert device.hostname == r"\\.\DISPLAY5"
    assert device.is_online is True
    assert device.display_index == 5
    assert device.resolution == (3840, 2160)
    assert DeviceCapability.VIDEO_PLAYBACK in device.capabilities
    assert device.metadata["renderer_projector_id"] == "proj-hdmi-local"
    assert device.metadata["connection_state"] == "attached"


def test_hdmi_discovery_backend_casts_through_renderer_url_transport():
    renderer_service = _FakeRendererService()
    backend = HDMIDiscoveryBackend(renderer_service=renderer_service)
    device = asyncio.run(backend.discover_devices())[0]

    session = asyncio.run(
        backend.cast_content(
            device,
            "http://127.0.0.1:8088/backend-static/blank.html",
            content_type="text/html",
            metadata={"content_mode": "blank"},
        )
    )

    assert session.device is device
    assert renderer_service.started == [
        (
            "proj-hdmi-local",
            "http://127.0.0.1:8088/backend-static/blank.html",
            "blank",
            {"content_mode": "blank"},
        )
    ]
    assert asyncio.run(backend.stop_casting(session)) is True
    assert renderer_service.stopped == ["proj-hdmi-local"]
