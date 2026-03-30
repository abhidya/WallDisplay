from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SceneRankBase(BaseModel):
    name: str
    orientation: str = "horizontal"
    scene_ids: List[int] = Field(default_factory=list)
    gap_px: int = 0
    rank_metadata: Dict[str, Any] = Field(default_factory=dict)


class SceneRankCreate(SceneRankBase):
    pass


class SceneRankUpdate(BaseModel):
    name: Optional[str] = None
    orientation: Optional[str] = None
    scene_ids: Optional[List[int]] = None
    gap_px: Optional[int] = None
    rank_metadata: Optional[Dict[str, Any]] = None


class SceneRankResponse(SceneRankBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
