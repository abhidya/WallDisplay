from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class MappingMask(BaseModel):
    id: str
    name: str
    file_name: str
    stored_path: str
    width: int
    height: int
    sort_order: int = 0


class MappingPoint(BaseModel):
    x: float
    y: float


class PolygonMaskCreateRequest(BaseModel):
    name: str
    points: List[MappingPoint] = Field(default_factory=list)


class MappingGroupTransform(BaseModel):
    scale: float = 1.0
    offset_x: float = 0
    offset_y: float = 0
    rotation: float = 0


class MappingGroup(BaseModel):
    id: str
    name: str
    mask_ids: List[str] = Field(default_factory=list)
    media_binding_type: str = "video"
    animation_id: Optional[str] = None
    animation_list_id: Optional[str] = None
    video_id: Optional[int] = None
    photo_id: Optional[int] = None
    media_list_id: Optional[int] = None
    photo_list_id: Optional[int] = None
    media_channel_id: Optional[int] = None
    media_directory_id: Optional[int] = None
    media_directory_ids: List[int] = Field(default_factory=list)
    direct_url: Optional[str] = None
    playlist_entries: List[str] = Field(default_factory=list)
    auto_advance: bool = True
    shuffle: bool = False
    z_index: int = 0
    visible: bool = True
    transform: MappingGroupTransform = Field(default_factory=MappingGroupTransform)
    fill_mode: str = "gradient"
    color_a: str = "#00bbf9"
    color_b: str = "#003049"


class MappingSceneBase(BaseModel):
    name: str
    canvas_width: int = 1280
    canvas_height: int = 720
    mask_mode: str = "luminance"
    masks: List[MappingMask] = Field(default_factory=list)
    groups: List[MappingGroup] = Field(default_factory=list)
    render_settings: Dict[str, Any] = Field(default_factory=dict)


class MappingSceneCreate(MappingSceneBase):
    pass


class MappingSceneUpdate(BaseModel):
    name: Optional[str] = None
    canvas_width: Optional[int] = None
    canvas_height: Optional[int] = None
    mask_mode: Optional[str] = None
    masks: Optional[List[MappingMask]] = None
    groups: Optional[List[MappingGroup]] = None
    render_settings: Optional[Dict[str, Any]] = None


class MappingSceneResponse(MappingSceneBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
