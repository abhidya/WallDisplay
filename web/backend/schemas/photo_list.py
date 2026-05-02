from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field, ConfigDict


class PhotoListBase(BaseModel):
    name: str
    category: str = "background"
    photo_ids: List[int] = Field(default_factory=list)
    playback_mode: str = "sequence"
    shuffle: bool = False
    loop: bool = True


class PhotoListCreate(PhotoListBase):
    pass


class PhotoListUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    photo_ids: Optional[List[int]] = None
    playback_mode: Optional[str] = None
    shuffle: Optional[bool] = None
    loop: Optional[bool] = None


class PhotoListResponse(PhotoListBase):
    id: int
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
