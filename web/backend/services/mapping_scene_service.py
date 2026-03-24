import os
import shutil
import uuid
from typing import Dict, List, Optional

from fastapi import UploadFile
from PIL import Image
from sqlalchemy.orm import Session

from models.mapping_scene import MappingScene
from schemas.mapping_scene import MappingMask, MappingSceneCreate, MappingSceneResponse, MappingSceneUpdate


class MappingSceneService:
    def __init__(self, db: Session):
        self.db = db
        self.upload_root = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "uploads", "mappings")

    def list_scenes(self) -> List[MappingSceneResponse]:
        scenes = self.db.query(MappingScene).order_by(MappingScene.updated_at.desc()).all()
        return [self._to_response(scene) for scene in scenes]

    def create_scene(self, data: MappingSceneCreate) -> MappingSceneResponse:
        scene = MappingScene(
            name=data.name,
            canvas_width=data.canvas_width,
            canvas_height=data.canvas_height,
            mask_mode=data.mask_mode,
            masks=[mask.model_dump() for mask in data.masks],
            groups=[group.model_dump() for group in data.groups],
            render_settings=data.render_settings,
        )
        self.db.add(scene)
        self.db.commit()
        self.db.refresh(scene)
        self._ensure_scene_dir(scene.id)
        return self._to_response(scene)

    def get_scene(self, scene_id: int) -> Optional[MappingSceneResponse]:
        scene = self.db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        return self._to_response(scene) if scene else None

    def update_scene(self, scene_id: int, update: MappingSceneUpdate) -> Optional[MappingSceneResponse]:
        scene = self.db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            return None
        data = update.model_dump(exclude_unset=True)
        if "masks" in data:
          data["masks"] = [mask.model_dump() if hasattr(mask, "model_dump") else mask for mask in data["masks"]]
        if "groups" in data:
          data["groups"] = [group.model_dump() if hasattr(group, "model_dump") else group for group in data["groups"]]
        for key, value in data.items():
            setattr(scene, key, value)
        self.db.commit()
        self.db.refresh(scene)
        return self._to_response(scene)

    def delete_scene(self, scene_id: int) -> bool:
        scene = self.db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            return False
        self.db.delete(scene)
        self.db.commit()
        scene_dir = self._scene_dir(scene_id)
        if os.path.isdir(scene_dir):
            shutil.rmtree(scene_dir, ignore_errors=True)
        return True

    async def upload_masks(self, scene_id: int, masks: List[UploadFile]) -> MappingSceneResponse:
        scene = self.db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            raise ValueError("Scene not found")
        mask_dir = os.path.join(self._ensure_scene_dir(scene_id), "masks")
        os.makedirs(mask_dir, exist_ok=True)
        existing_masks = list(scene.masks or [])
        sort_order = len(existing_masks)
        for upload in masks:
            suffix = os.path.splitext(upload.filename or "")[1].lower() or ".png"
            stored_name = f"{uuid.uuid4().hex}{suffix}"
            stored_path = os.path.join(mask_dir, stored_name)
            content = await upload.read()
            with open(stored_path, "wb") as fh:
                fh.write(content)
            image = Image.open(stored_path)
            rel_path = os.path.relpath(stored_path, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            existing_masks.append(
                MappingMask(
                    id=uuid.uuid4().hex,
                    name=os.path.splitext(upload.filename or stored_name)[0],
                    file_name=upload.filename or stored_name,
                    stored_path=rel_path.replace("\\", "/"),
                    width=image.width,
                    height=image.height,
                    sort_order=sort_order,
                ).model_dump()
            )
            sort_order += 1
        scene.masks = existing_masks
        self.db.commit()
        self.db.refresh(scene)
        return self._to_response(scene)

    def _scene_dir(self, scene_id: int) -> str:
        return os.path.join(self.upload_root, str(scene_id))

    def _ensure_scene_dir(self, scene_id: int) -> str:
        scene_dir = self._scene_dir(scene_id)
        os.makedirs(scene_dir, exist_ok=True)
        return scene_dir

    def _to_response(self, scene: MappingScene) -> MappingSceneResponse:
        return MappingSceneResponse(
            id=scene.id,
            name=scene.name,
            canvas_width=scene.canvas_width,
            canvas_height=scene.canvas_height,
            mask_mode=scene.mask_mode,
            masks=scene.masks or [],
            groups=scene.groups or [],
            render_settings=scene.render_settings or {},
            created_at=scene.created_at,
            updated_at=scene.updated_at,
        )
