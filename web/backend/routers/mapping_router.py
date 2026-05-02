import os
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.models.mapping_scene import MappingScene
from web.backend.schemas.mapping_scene import (
    MappingSceneCreate,
    MappingSceneResponse,
    MappingSceneUpdate,
    PolygonMaskCreateRequest,
)
from web.backend.services.mapping_scene_service import MappingSceneService
from web.backend.schemas.scene_rank import SceneRankCreate, SceneRankResponse, SceneRankUpdate
from web.backend.services.scene_rank_service import SceneRankService
from web.backend.schemas.scene_control_preset import (
    SceneControlPresetCreate,
    SceneControlPresetResponse,
    SceneControlPresetUpdate,
)
from web.backend.services.scene_control_preset_service import SceneControlPresetService
from web.backend.services.overlay_event_bus import notify_overlay_config_update
from web.backend.models.overlay import OverlayConfig


router = APIRouter(prefix="/api/mappings", tags=["mappings"])


def _notify_mapping_scene_dependents(db: Session, scene_id: int, reason: str) -> None:
    config_ids = [
        config_id
        for (config_id,) in db.query(OverlayConfig.id).filter(OverlayConfig.mapping_scene_id == scene_id).all()
    ]
    notify_overlay_config_update(config_ids, reason)


@router.get("/scenes", response_model=List[MappingSceneResponse])
def list_mapping_scenes(db: Session = Depends(get_db)):
    return MappingSceneService(db).list_scenes()


@router.get("/ranks", response_model=List[SceneRankResponse])
def list_scene_ranks(db: Session = Depends(get_db)):
    return SceneRankService(db).list_ranks()


@router.get("/scene-control-presets", response_model=List[SceneControlPresetResponse])
def list_scene_control_presets(db: Session = Depends(get_db)):
    return SceneControlPresetService(db).list_presets()


@router.post("/scene-control-presets", response_model=SceneControlPresetResponse)
def create_scene_control_preset(payload: SceneControlPresetCreate, db: Session = Depends(get_db)):
    try:
        return SceneControlPresetService(db).create_preset(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/scene-control-presets/{preset_id}", response_model=SceneControlPresetResponse)
def get_scene_control_preset(preset_id: int, db: Session = Depends(get_db)):
    preset = SceneControlPresetService(db).get_preset(preset_id)
    if not preset:
        raise HTTPException(status_code=404, detail="Scene control preset not found")
    return preset


@router.put("/scene-control-presets/{preset_id}", response_model=SceneControlPresetResponse)
def update_scene_control_preset(preset_id: int, payload: SceneControlPresetUpdate, db: Session = Depends(get_db)):
    try:
        preset = SceneControlPresetService(db).update_preset(preset_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not preset:
        raise HTTPException(status_code=404, detail="Scene control preset not found")
    return preset


@router.delete("/scene-control-presets/{preset_id}")
def delete_scene_control_preset(preset_id: int, db: Session = Depends(get_db)):
    deleted = SceneControlPresetService(db).delete_preset(preset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scene control preset not found")
    return {"success": True}


@router.post("/ranks", response_model=SceneRankResponse)
def create_scene_rank(payload: SceneRankCreate, db: Session = Depends(get_db)):
    try:
        return SceneRankService(db).create_rank(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/ranks/{rank_id}", response_model=SceneRankResponse)
def get_scene_rank(rank_id: int, db: Session = Depends(get_db)):
    rank = SceneRankService(db).get_rank(rank_id)
    if not rank:
        raise HTTPException(status_code=404, detail="Scene rank not found")
    return rank


@router.put("/ranks/{rank_id}", response_model=SceneRankResponse)
def update_scene_rank(rank_id: int, payload: SceneRankUpdate, db: Session = Depends(get_db)):
    try:
        rank = SceneRankService(db).update_rank(rank_id, payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not rank:
        raise HTTPException(status_code=404, detail="Scene rank not found")
    return rank


@router.delete("/ranks/{rank_id}")
def delete_scene_rank(rank_id: int, db: Session = Depends(get_db)):
    deleted = SceneRankService(db).delete_rank(rank_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scene rank not found")
    return {"success": True}


@router.post("/scenes", response_model=MappingSceneResponse)
def create_mapping_scene(payload: MappingSceneCreate, db: Session = Depends(get_db)):
    return MappingSceneService(db).create_scene(payload)


@router.get("/scenes/{scene_id}", response_model=MappingSceneResponse)
def get_mapping_scene(scene_id: int, db: Session = Depends(get_db)):
    scene = MappingSceneService(db).get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


@router.get("/scenes/{scene_id}/export")
def export_mapping_scene(scene_id: int, db: Session = Depends(get_db)):
    try:
        bundle_path = MappingSceneService(db).export_scene_bundle(scene_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(bundle_path, media_type="application/zip", filename=f"mapping_scene_{scene_id}.zip")


@router.post("/scenes/import", response_model=MappingSceneResponse)
async def import_mapping_scene(bundle: UploadFile = File(...), db: Session = Depends(get_db)):
    try:
        return await MappingSceneService(db).import_scene_bundle(bundle)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.put("/scenes/{scene_id}", response_model=MappingSceneResponse)
def update_mapping_scene(scene_id: int, payload: MappingSceneUpdate, db: Session = Depends(get_db)):
    scene = MappingSceneService(db).update_scene(scene_id, payload)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    _notify_mapping_scene_dependents(db, scene_id, "mapping_scene_updated")
    return scene


@router.delete("/scenes/{scene_id}")
def delete_mapping_scene(scene_id: int, db: Session = Depends(get_db)):
    deleted = MappingSceneService(db).delete_scene(scene_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Scene not found")
    return {"success": True}


@router.post("/scenes/{scene_id}/masks/upload", response_model=MappingSceneResponse)
async def upload_mapping_masks(scene_id: int, masks: List[UploadFile] = File(...), db: Session = Depends(get_db)):
    try:
        scene = await MappingSceneService(db).upload_masks(scene_id, masks)
        _notify_mapping_scene_dependents(db, scene_id, "mapping_masks_uploaded")
        return scene
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/scenes/{scene_id}/masks/polygon", response_model=MappingSceneResponse)
def create_polygon_mask(scene_id: int, payload: PolygonMaskCreateRequest, db: Session = Depends(get_db)):
    try:
        scene = MappingSceneService(db).create_polygon_mask(scene_id, payload.name, payload.points)
        _notify_mapping_scene_dependents(db, scene_id, "mapping_polygon_mask_created")
        return scene
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail == "Scene not found" else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.delete("/scenes/{scene_id}/masks/{mask_id}", response_model=MappingSceneResponse)
def delete_mapping_mask(scene_id: int, mask_id: str, db: Session = Depends(get_db)):
    try:
        scene = MappingSceneService(db).delete_mask(scene_id, mask_id)
        _notify_mapping_scene_dependents(db, scene_id, "mapping_mask_deleted")
        return scene
    except ValueError as exc:
        detail = str(exc)
        status_code = 404 if detail in {"Scene not found", "Mask not found"} else 400
        raise HTTPException(status_code=status_code, detail=detail) from exc


@router.get("/scenes/{scene_id}/masks/{mask_id}/file")
def get_mapping_mask_file(scene_id: int, mask_id: str, db: Session = Depends(get_db)):
    scene = db.query(MappingScene).filter(MappingScene.id == scene_id).first()
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    mask = next((item for item in (scene.masks or []) if item.get("id") == mask_id), None)
    if not mask:
        raise HTTPException(status_code=404, detail="Mask not found")
    backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    mask_path = os.path.join(backend_root, mask["stored_path"])
    if not os.path.exists(mask_path):
        raise HTTPException(status_code=404, detail="Mask file missing")
    return FileResponse(
        mask_path,
        media_type="image/png",
        headers={
            "Cache-Control": "public, max-age=31536000, immutable",
        },
    )
