from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SceneControlPresetBase(BaseModel):
    name: str
    scene_ids: List[int] = Field(default_factory=list)
    group_assignments: Dict[str, List[List[str]]] = Field(default_factory=dict)
    row_edits: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    rank_id: Optional[int] = None
    preset_metadata: Dict[str, Any] = Field(default_factory=dict)


class SceneControlPresetCreate(SceneControlPresetBase):
    pass


class SceneControlPresetUpdate(BaseModel):
    name: Optional[str] = None
    scene_ids: Optional[List[int]] = None
    group_assignments: Optional[Dict[str, List[List[str]]]] = None
    row_edits: Optional[Dict[str, Dict[str, Any]]] = None
    rank_id: Optional[int] = None
    preset_metadata: Optional[Dict[str, Any]] = None


class SceneControlPresetResponse(SceneControlPresetBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
