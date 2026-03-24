from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class MediaListBase(BaseModel):
    name: str
    category: str = "background"
    video_ids: List[int] = Field(default_factory=list)
    playback_mode: str = "sequence"
    shuffle: bool = False
    loop: bool = True


class MediaListCreate(MediaListBase):
    pass


class MediaListUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    video_ids: Optional[List[int]] = None
    playback_mode: Optional[str] = None
    shuffle: Optional[bool] = None
    loop: Optional[bool] = None


class MediaListResponse(MediaListBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
