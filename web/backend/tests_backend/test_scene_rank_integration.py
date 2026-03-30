from web.backend.models.mapping_scene import MappingScene
from web.backend.models.overlay import OverlayConfig
from web.backend.models.scene_rank import SceneRank
from web.backend.services.overlay_service import OverlayService


def test_mapping_rank_payload_includes_rank_layout_and_viewport(test_db):
    left_scene = MappingScene(
        name="Left Scene",
        canvas_width=1280,
        canvas_height=720,
        masks=[],
        groups=[{"id": "g-left", "name": "Span Group", "mask_ids": [], "layout_scope": "rank"}],
        render_settings={},
    )
    middle_scene = MappingScene(
        name="Middle Scene",
        canvas_width=1280,
        canvas_height=720,
        masks=[],
        groups=[{"id": "g-middle", "name": "Span Group", "mask_ids": [], "layout_scope": "rank"}],
        render_settings={},
    )
    test_db.add_all([left_scene, middle_scene])
    test_db.commit()
    test_db.refresh(left_scene)
    test_db.refresh(middle_scene)

    rank = SceneRank(
        name="Kitchen Wall",
        orientation="horizontal",
        scene_ids=[left_scene.id, middle_scene.id],
        gap_px=40,
        rank_metadata={},
    )
    test_db.add(rank)
    test_db.commit()

    config = OverlayConfig(
        name="Ranked Overlay",
        background_type="mapping",
        video_id=None,
        mapping_scene_id=middle_scene.id,
        video_transform={"x": 0, "y": 0, "scale": 1, "rotation": 0},
        widgets=[],
        api_configs={},
    )
    test_db.add(config)
    test_db.commit()
    test_db.refresh(config)

    payload = OverlayService(test_db).get_window_init_payload(config.id)

    assert payload.mapping_scene["rank_layout"]["rank_id"] == rank.id
    assert payload.mapping_scene["rank_layout"]["canvas_width"] == 2600
    assert payload.mapping_scene["scene_viewport"] == {
        "x": 1320,
        "y": 0,
        "width": 1280,
        "height": 720,
    }


def test_scene_rank_crud_endpoints(test_client):
    create_scene_payload = {
        "name": "Rank Scene A",
        "canvas_width": 1280,
        "canvas_height": 720,
        "mask_mode": "luminance",
        "masks": [],
        "groups": [],
        "render_settings": {},
    }
    first_scene = test_client.post("/api/mappings/scenes", json=create_scene_payload).json()
    second_scene = test_client.post("/api/mappings/scenes", json={**create_scene_payload, "name": "Rank Scene B"}).json()

    create_response = test_client.post(
        "/api/mappings/ranks",
        json={
            "name": "Scene Strip",
            "orientation": "horizontal",
            "scene_ids": [first_scene["id"], second_scene["id"]],
            "gap_px": 24,
            "rank_metadata": {},
        },
    )
    assert create_response.status_code == 200
    created = create_response.json()
    assert created["scene_ids"] == [first_scene["id"], second_scene["id"]]

    list_response = test_client.get("/api/mappings/ranks")
    assert list_response.status_code == 200
    assert any(rank["id"] == created["id"] for rank in list_response.json())

    update_response = test_client.put(
        f"/api/mappings/ranks/{created['id']}",
        json={"name": "Updated Strip", "gap_px": 32, "scene_ids": [second_scene["id"], first_scene["id"]]},
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["name"] == "Updated Strip"
    assert updated["gap_px"] == 32
    assert updated["scene_ids"] == [second_scene["id"], first_scene["id"]]
