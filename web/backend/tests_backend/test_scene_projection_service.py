import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import web.backend.routers.mapping_router as mapping_router
from web.backend.database.database import Base, get_db
from web.backend.models.mapping_scene import MappingScene
from web.backend.models.overlay import OverlayConfig
from web.backend.services.scene_projection_service import SceneProjectionService


@pytest.fixture
def db_session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    session = sessionmaker(autocommit=False, autoflush=False, bind=engine)()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


class FakeRendererService:
    def __init__(self):
        self.started = []
        self.stopped = []

    def start_projector_mode(self, projector_id, mode, options):
        self.started.append((projector_id, mode, options))
        return True

    def start_projector_url(self, projector_id, content_url, content_mode="url", options=None):
        self.started.append((projector_id, content_url, content_mode, options or {}))
        return True

    def get_renderer_status(self, projector_id):
        return {
            "projector_id": projector_id,
            "status": "projecting",
            "sender_status": {
                "type": "hdmi",
                "projection_state": "projecting",
            },
        }

    def stop_renderer(self, projector_id):
        self.stopped.append(projector_id)
        return True


class FakeOverlayCastPipeline:
    def __init__(self):
        self.started = []
        self.stopped = []

    async def start_cast(self, *, device_id, config_id, overlay_base_url, controls_hidden):
        self.started.append(
            {
                "device_id": device_id,
                "config_id": config_id,
                "overlay_base_url": overlay_base_url,
                "controls_hidden": controls_hidden,
            }
        )
        return {
            "session_id": "cast-session-1",
            "device_id": device_id,
            "config_id": config_id,
            "status": "preparing",
        }

    async def stop_cast(self, session_id):
        self.stopped.append(session_id)
        return True


def create_mapping_scene(db, name="Kitchen Wall"):
    scene = MappingScene(
        name=name,
        canvas_width=1280,
        canvas_height=720,
        mask_mode="luminance",
        masks=[],
        groups=[],
        render_settings={},
    )
    db.add(scene)
    db.commit()
    db.refresh(scene)
    return scene


@pytest.mark.anyio
async def test_hdmi_launch_creates_mapping_overlay_config_once(db_session):
    scene = create_mapping_scene(db_session)
    renderer = FakeRendererService()
    service = SceneProjectionService(db_session, renderer_service=renderer)

    first = await service.launch(
        scene.id,
        target_type="hdmi",
        target_id="proj-hdmi-local",
        overlay_base_url="http://controller",
    )
    second = await service.launch(
        scene.id,
        target_type="hdmi",
        target_id="proj-hdmi-local",
        overlay_base_url="http://controller",
        controls_hidden=False,
    )

    assert first["transport"] == "hdmi"
    assert first["overlay_config"]["background_type"] == "mapping"
    assert first["overlay_config"]["mapping_scene_id"] == scene.id
    assert second["overlay_config"]["id"] == first["overlay_config"]["id"]
    assert db_session.query(OverlayConfig).filter(OverlayConfig.mapping_scene_id == scene.id).count() == 1
    assert renderer.started == [
        (
            "proj-hdmi-local",
            f"http://controller/backend-static/overlay_window.html?projector_id=proj-hdmi-local&mode=overlay&config_id={first['overlay_config']['id']}&controls=hidden&projection_mode=1",
            "overlay",
            {"config_id": first["overlay_config"]["id"], "controls": "hidden", "projection_mode": "1"},
        ),
        (
            "proj-hdmi-local",
            f"http://controller/backend-static/overlay_window.html?projector_id=proj-hdmi-local&mode=overlay&config_id={first['overlay_config']['id']}&projection_mode=1",
            "overlay",
            {"config_id": first["overlay_config"]["id"], "controls": "visible", "projection_mode": "1"},
        ),
    ]


@pytest.mark.anyio
async def test_dlna_launch_uses_same_mapping_overlay_config(db_session):
    scene = create_mapping_scene(db_session)
    cast_pipeline = FakeOverlayCastPipeline()
    service = SceneProjectionService(db_session, overlay_cast_pipeline=cast_pipeline)

    result = await service.launch(
        scene.id,
        target_type="dlna",
        target_id="dlna-living-room",
        overlay_base_url="http://controller",
    )

    assert result["transport"] == "dlna"
    assert result["cast_session"]["session_id"] == "cast-session-1"
    assert cast_pipeline.started == [
        {
            "device_id": "dlna-living-room",
            "config_id": result["overlay_config"]["id"],
            "overlay_base_url": "http://controller",
            "controls_hidden": True,
        }
    ]


@pytest.mark.anyio
async def test_scene_projection_stop_dispatches_by_transport(db_session):
    renderer = FakeRendererService()
    cast_pipeline = FakeOverlayCastPipeline()
    service = SceneProjectionService(db_session, renderer_service=renderer, overlay_cast_pipeline=cast_pipeline)

    hdmi = await service.stop(target_type="hdmi", target_id="proj-hdmi-local")
    dlna = await service.stop(target_type="dlna", target_id="cast-session-1")

    assert hdmi == {"status": "stopped", "transport": "hdmi", "target_id": "proj-hdmi-local"}
    assert dlna == {"status": "stopped", "transport": "dlna", "target_id": "cast-session-1"}
    assert renderer.stopped == ["proj-hdmi-local"]
    assert cast_pipeline.stopped == ["cast-session-1"]


@pytest.mark.anyio
async def test_scene_projection_rejects_invalid_scene_and_target(db_session):
    service = SceneProjectionService(db_session, renderer_service=FakeRendererService())

    with pytest.raises(ValueError, match="Mapping scene not found"):
        await service.launch(404, target_type="hdmi", target_id="proj-hdmi-local", overlay_base_url="http://controller")

    with pytest.raises(ValueError, match="target_type must be hdmi or dlna"):
        await service.launch(404, target_type="airplay", target_id="device", overlay_base_url="http://controller")

    with pytest.raises(ValueError, match="target_id is required"):
        await service.stop(target_type="hdmi", target_id="")


def test_project_scene_route_uses_projection_service_and_default_base_url(db_session, monkeypatch):
    calls = {}

    class RouteFakeSceneProjectionService:
        def __init__(self, db):
            self.db = db

        async def launch(self, scene_id, *, target_type, target_id, overlay_base_url, controls_hidden):
            calls["launch"] = {
                "scene_id": scene_id,
                "target_type": target_type,
                "target_id": target_id,
                "overlay_base_url": overlay_base_url,
                "controls_hidden": controls_hidden,
            }
            return {"status": "launched", "transport": target_type, "target_id": target_id}

        async def stop(self, *, target_type, target_id):
            calls["stop"] = {"target_type": target_type, "target_id": target_id}
            return {"status": "stopped", "transport": target_type, "target_id": target_id}

    monkeypatch.setattr(mapping_router, "SceneProjectionService", RouteFakeSceneProjectionService)
    app = FastAPI()
    app.include_router(mapping_router.router)
    def override_db():
        yield db_session

    app.dependency_overrides[get_db] = override_db
    client = TestClient(app)

    launch_response = client.post(
        "/api/mappings/scenes/12/project",
        json={"target_type": "dlna", "target_id": "dlna-living-room"},
    )
    stop_response = client.post(
        "/api/mappings/scenes/project/stop",
        json={"target_type": "dlna", "target_id": "cast-session-1"},
    )

    assert launch_response.status_code == 200
    assert stop_response.status_code == 200
    assert calls["launch"] == {
        "scene_id": 12,
        "target_type": "dlna",
        "target_id": "dlna-living-room",
        "overlay_base_url": "http://testserver",
        "controls_hidden": True,
    }
    assert calls["stop"] == {"target_type": "dlna", "target_id": "cast-session-1"}
