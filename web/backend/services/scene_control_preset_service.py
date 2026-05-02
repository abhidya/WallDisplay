from typing import Dict, List, Optional

from sqlalchemy.orm import Session

from web.backend.models.mapping_scene import MappingScene
from web.backend.models.scene_control_preset import SceneControlPreset
from web.backend.models.scene_rank import SceneRank
from web.backend.schemas.scene_control_preset import (
    SceneControlPresetCreate,
    SceneControlPresetResponse,
    SceneControlPresetUpdate,
)


class SceneControlPresetService:
    def __init__(self, db: Session):
        self.db = db

    def list_presets(self) -> List[SceneControlPresetResponse]:
        presets = self.db.query(SceneControlPreset).order_by(SceneControlPreset.updated_at.desc()).all()
        return [self._to_response(preset) for preset in presets]

    def get_preset(self, preset_id: int) -> Optional[SceneControlPresetResponse]:
        preset = self.db.query(SceneControlPreset).filter(SceneControlPreset.id == preset_id).first()
        return self._to_response(preset) if preset else None

    def create_preset(self, payload: SceneControlPresetCreate) -> SceneControlPresetResponse:
        scene_ids = self._normalize_scene_ids(payload.scene_ids or [])
        self._validate_scene_ids(scene_ids)
        self._validate_rank_id(payload.rank_id)
        preset = SceneControlPreset(
            name=payload.name,
            scene_ids=scene_ids,
            group_assignments=self._normalize_group_assignments(payload.group_assignments or {}),
            row_edits=self._normalize_row_edits(payload.row_edits or {}),
            rank_id=payload.rank_id,
            preset_metadata=payload.preset_metadata or {},
        )
        self.db.add(preset)
        self.db.commit()
        self.db.refresh(preset)
        return self._to_response(preset)

    def update_preset(self, preset_id: int, payload: SceneControlPresetUpdate) -> Optional[SceneControlPresetResponse]:
        preset = self.db.query(SceneControlPreset).filter(SceneControlPreset.id == preset_id).first()
        if not preset:
            return None

        data = payload.model_dump(exclude_unset=True)
        if "scene_ids" in data:
            scene_ids = self._normalize_scene_ids(data["scene_ids"] or [])
            self._validate_scene_ids(scene_ids)
            preset.scene_ids = scene_ids
        if "name" in data:
            preset.name = data["name"]
        if "group_assignments" in data:
            preset.group_assignments = self._normalize_group_assignments(data["group_assignments"] or {})
        if "row_edits" in data:
            preset.row_edits = self._normalize_row_edits(data["row_edits"] or {})
        if "rank_id" in data:
            self._validate_rank_id(data["rank_id"])
            preset.rank_id = data["rank_id"]
        if "preset_metadata" in data:
            preset.preset_metadata = data["preset_metadata"] or {}

        self.db.commit()
        self.db.refresh(preset)
        return self._to_response(preset)

    def delete_preset(self, preset_id: int) -> bool:
        preset = self.db.query(SceneControlPreset).filter(SceneControlPreset.id == preset_id).first()
        if not preset:
            return False
        self.db.delete(preset)
        self.db.commit()
        return True

    def _normalize_scene_ids(self, scene_ids: List[int]) -> List[int]:
        normalized: List[int] = []
        for scene_id in scene_ids:
            try:
                value = int(scene_id)
            except (TypeError, ValueError):
                continue
            if value > 0:
                normalized.append(value)
        return normalized

    def _normalize_group_assignments(self, assignments: Dict[str, List[List[str]]]) -> Dict[str, List[List[str]]]:
        normalized: Dict[str, List[List[str]]] = {}
        for scene_id, buckets in assignments.items():
            try:
                scene_key = str(int(scene_id))
            except (TypeError, ValueError):
                continue
            normalized[scene_key] = []
            for bucket in buckets or []:
                normalized_bucket: List[str] = []
                for group_id in bucket or []:
                    value = str(group_id or "").strip()
                    if not value:
                        continue
                    normalized_bucket.append(value)
                normalized[scene_key].append(normalized_bucket)
        return normalized

    def _normalize_row_edits(self, row_edits: Dict[str, Dict[str, object]]) -> Dict[str, Dict[str, object]]:
        normalized: Dict[str, Dict[str, object]] = {}
        for row_index, row_edit in row_edits.items():
            try:
                row_key = str(int(row_index))
            except (TypeError, ValueError):
                continue
            normalized[row_key] = dict(row_edit or {})
        return normalized

    def _validate_scene_ids(self, scene_ids: List[int]) -> None:
        if not scene_ids:
            return
        existing_ids = {
            scene_id
            for (scene_id,) in self.db.query(MappingScene.id).filter(MappingScene.id.in_(scene_ids)).all()
        }
        missing = [scene_id for scene_id in scene_ids if scene_id not in existing_ids]
        if missing:
            raise ValueError(f"Unknown mapping scene ids: {missing}")

    def _validate_rank_id(self, rank_id: Optional[int]) -> None:
        if rank_id is None:
            return
        exists = self.db.query(SceneRank.id).filter(SceneRank.id == rank_id).first()
        if not exists:
            raise ValueError(f"Unknown scene rank id: {rank_id}")

    def _to_response(self, preset: SceneControlPreset) -> SceneControlPresetResponse:
        return SceneControlPresetResponse(
            id=preset.id,
            name=preset.name,
            scene_ids=[int(scene_id) for scene_id in (preset.scene_ids or [])],
            group_assignments=preset.group_assignments or {},
            row_edits=preset.row_edits or {},
            rank_id=preset.rank_id,
            preset_metadata=preset.preset_metadata or {},
            created_at=preset.created_at,
            updated_at=preset.updated_at,
        )
