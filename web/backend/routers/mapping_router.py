import os
from typing import List

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from database.database import get_db
from models.mapping_scene import MappingScene
from schemas.mapping_scene import (
    MappingSceneCreate,
    MappingSceneResponse,
    MappingSceneUpdate,
    PolygonMaskCreateRequest,
)
from services.mapping_scene_service import MappingSceneService
from services.overlay_event_bus import notify_overlay_config_update
from models.overlay import OverlayConfig


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


@router.post("/scenes", response_model=MappingSceneResponse)
def create_mapping_scene(payload: MappingSceneCreate, db: Session = Depends(get_db)):
    return MappingSceneService(db).create_scene(payload)


@router.get("/scenes/{scene_id}", response_model=MappingSceneResponse)
def get_mapping_scene(scene_id: int, db: Session = Depends(get_db)):
    scene = MappingSceneService(db).get_scene(scene_id)
    if not scene:
        raise HTTPException(status_code=404, detail="Scene not found")
    return scene


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
    return FileResponse(mask_path, media_type="image/png")
