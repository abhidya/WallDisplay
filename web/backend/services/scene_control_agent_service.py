"""Agent-oriented scene control helpers used by MCP servers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.database.database import ensure_sqlite_schema_compatibility
from web.backend.models.mapping_scene import MappingScene
from web.backend.models.media_list import MediaList
from web.backend.models.scene_control_preset import SceneControlPreset
from web.backend.models.scene_rank import SceneRank
from web.backend.models.video import VideoModel
from web.backend.schemas.mapping_scene import MappingPoint, MappingSceneCreate, MappingSceneUpdate
from web.backend.schemas.media_list import MediaListCreate
from web.backend.schemas.scene_control_preset import SceneControlPresetCreate
from web.backend.schemas.scene_rank import SceneRankCreate
from web.backend.services.mapping_scene_service import MappingSceneService
from web.backend.services.media_list_service import MediaListService
from web.backend.services.scene_control_preset_service import SceneControlPresetService
from web.backend.services.scene_rank_service import SceneRankService


def _slug(value: str, fallback: str = "item") -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", str(value or "").strip()).strip("-").lower()
    return clean or fallback


def _model_dump(value: Any) -> Dict[str, Any]:
    return value.model_dump(mode="json") if hasattr(value, "model_dump") else dict(value)


def _unique_model_name(db: Session, model: Any, base_name: str, fallback: str = "Item") -> str:
    base = str(base_name or fallback).strip() or fallback
    existing = {name for (name,) in db.query(model.name).all()}
    if base not in existing:
        return base
    index = 2
    while f"{base} ({index})" in existing:
        index += 1
    return f"{base} ({index})"


def _unique_scene_name(db: Session, base_name: str) -> str:
    return _unique_model_name(db, MappingScene, base_name, fallback="Scene")


def _full_canvas_points(width: int, height: int) -> List[MappingPoint]:
    return [
        MappingPoint(x=0, y=0),
        MappingPoint(x=width, y=0),
        MappingPoint(x=width, y=height),
        MappingPoint(x=0, y=height),
    ]


def _normalize_clients(clients: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(clients, list) or not clients:
        raise ValueError("clients must be a non-empty list")
    normalized: List[Dict[str, Any]] = []
    for index, client in enumerate(clients):
        if not isinstance(client, dict):
            raise ValueError(f"client at index {index} must be an object")
        name = str(client.get("name") or client.get("id") or f"wall-{index + 1}").strip()
        width = int(client.get("canvas_width") or client.get("width") or 1280)
        height = int(client.get("canvas_height") or client.get("height") or 720)
        if width <= 0 or height <= 0:
            raise ValueError(f"client {name} has invalid canvas size")
        normalized.append({
            **client,
            "name": name,
            "canvas_width": width,
            "canvas_height": height,
            "metadata": dict(client.get("metadata") or {}),
        })
    return normalized


def _normalize_pattern_layers(pattern_layers: Optional[List[Dict[str, Any]]]) -> List[Dict[str, Any]]:
    if not pattern_layers:
        return [
            {"name": "Soft Ripple Pattern", "color_a": "#0b3954", "color_b": "#087e8b", "z_index": 10},
            {"name": "Light Caustic Pattern", "color_a": "#bfd7ea", "color_b": "#5bc0eb", "z_index": 20},
        ]
    if not isinstance(pattern_layers, list):
        raise ValueError("pattern_layers must be a list")
    normalized: List[Dict[str, Any]] = []
    for index, layer in enumerate(pattern_layers):
        if not isinstance(layer, dict):
            raise ValueError(f"pattern layer at index {index} must be an object")
        normalized.append({
            "name": str(layer.get("name") or f"Pattern {index + 1}"),
            "media_binding_type": layer.get("media_binding_type") or "pattern",
            "fill_mode": layer.get("fill_mode") or "gradient",
            "color_a": layer.get("color_a") or "#00bbf9",
            "color_b": layer.get("color_b") or "#003049",
            "z_index": int(layer.get("z_index") if layer.get("z_index") is not None else 10 + index),
            "direct_url": layer.get("direct_url") or "",
            "animation_id": layer.get("animation_id"),
            "animation_list_id": layer.get("animation_list_id"),
            "visible": layer.get("visible", True) is not False,
            "transform": dict(layer.get("transform") or {"scale": 1, "offset_x": 0, "offset_y": 0, "rotation": 0}),
        })
    return normalized


def _video_ids_exist(db: Session, video_ids: List[int]) -> List[int]:
    normalized = [int(video_id) for video_id in (video_ids or []) if int(video_id) > 0]
    if not normalized:
        return []
    existing = {
        video_id for (video_id,) in db.query(VideoModel.id).filter(VideoModel.id.in_(normalized)).all()
    }
    missing = [video_id for video_id in normalized if video_id not in existing]
    if missing:
        raise ValueError(f"Unknown video ids: {missing}")
    return normalized


def list_mapping_scenes(db: Session) -> List[Dict[str, Any]]:
    ensure_sqlite_schema_compatibility()
    return [_model_dump(scene) for scene in MappingSceneService(db).list_scenes()]


def create_mapping_scene(
    db: Session,
    name: str,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    groups: Optional[List[Dict[str, Any]]] = None,
    masks: Optional[List[Dict[str, Any]]] = None,
    render_settings: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    if not str(name or "").strip():
        raise ValueError("name is required")
    scene = MappingSceneService(db).create_scene(MappingSceneCreate(
        name=_unique_scene_name(db, name),
        canvas_width=max(1, int(canvas_width or 1280)),
        canvas_height=max(1, int(canvas_height or 720)),
        mask_mode="luminance",
        masks=masks or [],
        groups=groups or [],
        render_settings=render_settings or {"background": "#000000"},
    ))
    return _model_dump(scene)


def add_polygon_mask(db: Session, scene_id: int, name: str, points: List[Dict[str, float]]) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    if not isinstance(points, list) or len(points) < 3:
        raise ValueError("polygon mask requires at least 3 points")
    mapping_points = [MappingPoint(x=float(point["x"]), y=float(point["y"])) for point in points]
    scene = MappingSceneService(db).create_polygon_mask(int(scene_id), name, mapping_points)
    return _model_dump(scene)


def update_scene_groups(db: Session, scene_id: int, groups: List[Dict[str, Any]]) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    current = MappingSceneService(db).get_scene(int(scene_id))
    if not current:
        raise ValueError("Scene not found")
    scene = MappingSceneService(db).update_scene(int(scene_id), MappingSceneUpdate(groups=groups))
    if not scene:
        raise ValueError("Scene not found")
    return _model_dump(scene)


def create_scene_rank(db: Session, name: str, scene_ids: List[int], gap_px: int = 0, orientation: str = "horizontal") -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    rank = SceneRankService(db).create_rank(SceneRankCreate(
        name=_unique_model_name(db, SceneRank, name, fallback="Scene Rank"),
        orientation=orientation or "horizontal",
        scene_ids=[int(scene_id) for scene_id in scene_ids],
        gap_px=max(0, int(gap_px or 0)),
        rank_metadata={},
    ))
    return _model_dump(rank)


def create_scene_control_preset(
    db: Session,
    name: str,
    scene_ids: List[int],
    group_assignments: Optional[Dict[str, List[List[str]]]] = None,
    row_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    rank_id: Optional[int] = None,
    preset_metadata: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    preset = SceneControlPresetService(db).create_preset(SceneControlPresetCreate(
        name=_unique_model_name(db, SceneControlPreset, name, fallback="Scene Control Preset"),
        scene_ids=[int(scene_id) for scene_id in scene_ids],
        group_assignments=group_assignments or {},
        row_edits=row_edits or {},
        rank_id=int(rank_id) if rank_id else None,
        preset_metadata=preset_metadata or {},
    ))
    return _model_dump(preset)


def create_scene_across_clients(
    db: Session,
    name: str,
    clients: List[Dict[str, Any]],
    group_template: Optional[List[Dict[str, Any]]] = None,
    gap_px: int = 0,
    create_preset: bool = True,
) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    normalized_clients = _normalize_clients(clients)
    scenes: List[Dict[str, Any]] = []
    assignments: Dict[str, List[List[str]]] = {}
    template = group_template or []

    for client_index, client in enumerate(normalized_clients):
        scene_name = _unique_scene_name(db, f"{name} - {client['name']}")
        scene = MappingSceneService(db).create_scene(MappingSceneCreate(
            name=scene_name,
            canvas_width=client["canvas_width"],
            canvas_height=client["canvas_height"],
            mask_mode="luminance",
            masks=[],
            groups=[],
            render_settings={"background": "#000000", "client": client},
        ))
        service = MappingSceneService(db)
        scene_with_mask = service.create_polygon_mask(scene.id, "Full Canvas", _full_canvas_points(scene.canvas_width, scene.canvas_height))
        full_mask_id = scene_with_mask.masks[-1].id if scene_with_mask.masks else None
        groups: List[Dict[str, Any]] = []
        for group_index, template_group in enumerate(template):
            group_id = f"{_slug(template_group.get('id') or template_group.get('name') or 'group')}-{client_index + 1}-{group_index + 1}"
            groups.append({
                "id": group_id,
                "name": template_group.get("name") or f"Group {group_index + 1}",
                "mask_ids": [full_mask_id] if full_mask_id else [],
                "layout_scope": template_group.get("layout_scope") or "scene",
                "media_binding_type": template_group.get("media_binding_type") or "video",
                "animation_id": template_group.get("animation_id"),
                "animation_list_id": template_group.get("animation_list_id"),
                "video_id": template_group.get("video_id"),
                "photo_id": template_group.get("photo_id"),
                "media_list_id": template_group.get("media_list_id"),
                "photo_list_id": template_group.get("photo_list_id"),
                "media_channel_id": template_group.get("media_channel_id"),
                "media_directory_id": template_group.get("media_directory_id"),
                "media_directory_ids": template_group.get("media_directory_ids") or [],
                "direct_url": template_group.get("direct_url") or "",
                "playlist_entries": template_group.get("playlist_entries") or [],
                "auto_advance": template_group.get("auto_advance", True) is not False,
                "shuffle": bool(template_group.get("shuffle", False)),
                "z_index": int(template_group.get("z_index") or group_index),
                "visible": template_group.get("visible", True) is not False,
                "transform": template_group.get("transform") or {"scale": 1, "offset_x": 0, "offset_y": 0, "rotation": 0},
                "fill_mode": template_group.get("fill_mode") or "gradient",
                "color_a": template_group.get("color_a") or "#00bbf9",
                "color_b": template_group.get("color_b") or "#003049",
            })
        updated = service.update_scene(scene.id, MappingSceneUpdate(groups=groups))
        scene_dict = _model_dump(updated)
        scenes.append(scene_dict)
        assignments[str(scene.id)] = [[group["id"]] for group in groups]

    scene_ids = [scene["id"] for scene in scenes]
    rank = create_scene_rank(db, f"{name} Rank", scene_ids, gap_px=gap_px) if len(scene_ids) > 1 else None
    preset = None
    if create_preset:
        preset = create_scene_control_preset(
            db,
            f"{name} Preset",
            scene_ids,
            group_assignments=assignments,
            row_edits={},
            rank_id=rank["id"] if rank else None,
            preset_metadata={"created_by": "mcp_scene_control", "clients": normalized_clients},
        )
    return {"scenes": scenes, "rank": rank, "preset": preset, "group_assignments": assignments}


def create_all_walls_scene_from_media(
    db: Session,
    name: str,
    clients: List[Dict[str, Any]],
    background_video_ids: List[int],
    pattern_layers: Optional[List[Dict[str, Any]]] = None,
    gap_px: int = 0,
    create_preset: bool = True,
    use_media_list: bool = False,
) -> Dict[str, Any]:
    ensure_sqlite_schema_compatibility()
    video_ids = _video_ids_exist(db, background_video_ids)
    if not video_ids:
        raise ValueError("background_video_ids must include at least one existing video id")
    normalized_patterns = _normalize_pattern_layers(pattern_layers)
    media_list = None
    if use_media_list:
        media_list = MediaListService(db).create_media_list(MediaListCreate(
            name=_unique_model_name(db, MediaList, f"{name} Fish Backgrounds", fallback="Fish Backgrounds"),
            category="fish",
            video_ids=video_ids,
            playback_mode="sequence",
            shuffle=True,
            loop=True,
        ))
    template: List[Dict[str, Any]] = []
    template.append({
        "id": "fish-background",
        "name": "Fish Background",
        "media_binding_type": "media_list" if media_list else "video",
        "media_list_id": media_list.id if media_list else None,
        "video_id": None if media_list else video_ids[0],
        "layout_scope": "scene",
        "z_index": 0,
        "fill_mode": "media",
        "color_a": "#001219",
        "color_b": "#005f73",
    })
    for index, pattern in enumerate(normalized_patterns):
        template.append({
            "id": f"pattern-{index + 1}",
            "name": pattern["name"],
            "media_binding_type": pattern.get("media_binding_type") or "pattern",
            "direct_url": pattern.get("direct_url") or "",
            "animation_id": pattern.get("animation_id"),
            "animation_list_id": pattern.get("animation_list_id"),
            "layout_scope": "scene",
            "z_index": int(pattern.get("z_index") or 10 + index),
            "fill_mode": pattern.get("fill_mode") or "gradient",
            "color_a": pattern.get("color_a") or "#00bbf9",
            "color_b": pattern.get("color_b") or "#003049",
            "visible": pattern.get("visible", True),
            "transform": pattern.get("transform") or {"scale": 1, "offset_x": 0, "offset_y": 0, "rotation": 0},
        })
    result = create_scene_across_clients(
        db,
        name=name,
        clients=clients,
        group_template=template,
        gap_px=gap_px,
        create_preset=create_preset,
    )

    # Round-robin fixed video bindings when not using media list.
    if not media_list:
        service = MappingSceneService(db)
        refreshed_scenes: List[Dict[str, Any]] = []
        for index, scene in enumerate(result["scenes"]):
            scene_obj = service.get_scene(scene["id"])
            groups = [_model_dump(group) for group in scene_obj.groups]
            for group in groups:
                if group.get("id", "").startswith("fish-background"):
                    group["video_id"] = video_ids[index % len(video_ids)]
            updated = service.update_scene(scene["id"], MappingSceneUpdate(groups=groups))
            refreshed_scenes.append(_model_dump(updated))
        result["scenes"] = refreshed_scenes

    result["media_list"] = _model_dump(media_list) if media_list else None
    result["background_video_ids"] = video_ids
    result["pattern_layers"] = normalized_patterns
    return result
