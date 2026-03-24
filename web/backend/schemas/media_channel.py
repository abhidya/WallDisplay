from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, Field


class MediaChannelBase(BaseModel):
    name: str
    media_list_id: int
    current_video_id: Optional[int] = None
    current_index: int = 0
    playback_state: Dict[str, Any] = Field(default_factory=dict)


class MediaChannelCreate(MediaChannelBase):
    pass


class MediaChannelUpdate(BaseModel):
    name: Optional[str] = None
    media_list_id: Optional[int] = None
    current_video_id: Optional[int] = None
    current_index: Optional[int] = None
    playback_state: Optional[Dict[str, Any]] = None


class MediaChannelResponse(MediaChannelBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
