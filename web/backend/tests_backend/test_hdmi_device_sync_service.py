from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from web.backend.database.database import Base
from web.backend.models.device import DeviceModel
from web.backend.services.hdmi_device_sync_service import HDMIDeviceSyncService


class _FakeRendererService:
    def __init__(self, projectors):
        self._projectors = projectors

    def list_projectors(self):
        return list(self._projectors)


class _FakeRuntime:
    def __init__(self):
        self.updates = []

    def update_device_status(self, **kwargs):
        self.updates.append(kwargs)


def _session(tmp_path):
    engine = create_engine(f"sqlite:///{tmp_path / 'hdmi-devices.db'}", connect_args={"check_same_thread": False})
    Base.metadata.create_all(bind=engine)
    session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    return session_factory()


def _hdmi_projector(connection_state="attached", projection_state="projecting"):
    return {
        "id": "proj-hdmi-local",
        "name": "HDMI Projector",
        "sender": "hdmi",
        "target_name": r"\\.\DISPLAY5",
        "content_modes": ["identify", "overlay", "blank", "scene"],
        "runtime_status": {
            "sender_status": {
                "target": r"\\.\DISPLAY5",
                "connection_state": connection_state,
                "projection_state": projection_state,
                "power_state": "manual_on",
                "content_url": "http://127.0.0.1:8088/backend-static/video.html",
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
    }


def test_sync_configured_projectors_creates_managed_hdmi_device(tmp_path):
    db = _session(tmp_path)
    runtime = _FakeRuntime()
    service = HDMIDeviceSyncService(
        db=db,
        runtime=runtime,
        renderer_service=_FakeRendererService([_hdmi_projector()]),
    )

    synced = service.sync_configured_projectors()

    assert len(synced) == 1
    device = db.query(DeviceModel).filter(DeviceModel.name == "proj-hdmi-local").one()
    assert device.type == "hdmi"
    assert device.hostname == r"\\.\DISPLAY5"
    assert device.friendly_name == "HDMI Projector"
    assert device.status == "connected"
    assert device.is_playing is True
    assert device.current_video.endswith("/backend-static/video.html")
    assert device.config["casting_method"] == "hdmi"
    assert device.config["managed_by"] == "renderer_config"
    assert device.config["renderer_projector_id"] == "proj-hdmi-local"
    assert device.config["connection_state"] == "attached"
    assert device.config["projection_state"] == "projecting"
    assert runtime.updates[-1] == {
        "device_name": "proj-hdmi-local",
        "status": "connected",
        "is_playing": True,
        "current_video": "http://127.0.0.1:8088/backend-static/video.html",
    }


def test_sync_configured_projectors_updates_hdmi_detached_state(tmp_path):
    db = _session(tmp_path)
    runtime = _FakeRuntime()
    service = HDMIDeviceSyncService(
        db=db,
        runtime=runtime,
        renderer_service=_FakeRendererService([_hdmi_projector()]),
    )
    service.sync_configured_projectors()

    service.renderer_service = _FakeRendererService([_hdmi_projector(connection_state="detached", projection_state="idle")])
    service.sync_configured_projectors()

    device = db.query(DeviceModel).filter(DeviceModel.name == "proj-hdmi-local").one()
    assert device.status == "disconnected"
    assert device.is_playing is False
    assert device.config["connection_state"] == "detached"
    assert device.config["projection_state"] == "idle"
    assert runtime.updates[-1]["status"] == "disconnected"
    assert runtime.updates[-1]["is_playing"] is False
