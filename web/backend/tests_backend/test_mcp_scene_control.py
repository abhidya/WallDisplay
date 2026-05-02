from web.backend.models.mapping_scene import MappingScene
from web.backend.models.scene_control_preset import SceneControlPreset
from web.backend.models.scene_rank import SceneRank
from web.backend.models.video import VideoModel
from web.backend.services.scene_control_agent_service import (
    create_all_walls_scene_from_media,
    create_scene_across_clients,
)


def _add_video(db, name="Fish", path="/tmp/fish.mp4"):
    video = VideoModel(
        name=name,
        path=path,
        file_name=path.rsplit("/", 1)[-1],
        file_size=1024,
        category="fish",
        source_type="test",
        has_subtitle=False,
    )
    db.add(video)
    db.commit()
    db.refresh(video)
    return video


def test_create_scene_across_clients_creates_scenes_rank_and_preset(test_db):
    result = create_scene_across_clients(
        test_db,
        name="Wall Setup",
        clients=[
            {"name": "left", "canvas_width": 640, "canvas_height": 360},
            {"name": "right", "canvas_width": 640, "canvas_height": 360},
        ],
        group_template=[{"id": "background", "name": "Background", "z_index": 0}],
        gap_px=12,
        create_preset=True,
    )

    assert len(result["scenes"]) == 2
    assert result["rank"]["scene_ids"] == [scene["id"] for scene in result["scenes"]]
    assert result["rank"]["gap_px"] == 12
    assert result["preset"]["scene_ids"] == [scene["id"] for scene in result["scenes"]]
    stored_scene = test_db.query(MappingScene).filter(MappingScene.id == result["scenes"][0]["id"]).first()
    assert stored_scene.masks
    assert stored_scene.groups[0]["mask_ids"] == [stored_scene.masks[0]["id"]]


def test_create_all_walls_scene_from_media_maps_fish_background_and_patterns(test_db):
    first = _add_video(test_db, "Fish One", "/tmp/fish-one.mp4")
    second = _add_video(test_db, "Fish Two", "/tmp/fish-two.mp4")

    result = create_all_walls_scene_from_media(
        test_db,
        name="Fish Walls",
        clients=[
            {"name": "north", "canvas_width": 800, "canvas_height": 600},
            {"name": "south", "canvas_width": 800, "canvas_height": 600},
        ],
        background_video_ids=[first.id, second.id],
        pattern_layers=[{"name": "Caustics", "color_a": "#111111", "color_b": "#222222", "z_index": 10}],
        use_media_list=False,
    )

    assert len(result["scenes"]) == 2
    assert result["background_video_ids"] == [first.id, second.id]
    for index, scene_payload in enumerate(result["scenes"]):
        scene = test_db.query(MappingScene).filter(MappingScene.id == scene_payload["id"]).first()
        groups = scene.groups
        assert groups[0]["name"] == "Fish Background"
        assert groups[0]["media_binding_type"] == "video"
        assert groups[0]["video_id"] == [first.id, second.id][index]
        assert groups[1]["name"] == "Caustics"
        assert groups[1]["fill_mode"] == "gradient"
        assert groups[1]["z_index"] == 10
    assert test_db.query(SceneRank).count() == 1
    assert test_db.query(SceneControlPreset).count() == 1
