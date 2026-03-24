from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
from datetime import datetime

class WidgetPosition(BaseModel):
    x: Union[int, float]
    y: Union[int, float]

class WidgetSize(BaseModel):
    width: Union[int, float]
    height: Union[int, float]

class Widget(BaseModel):
    id: str
    type: str  # 'weather', 'time', 'transit', 'lights'
    position: WidgetPosition
    size: WidgetSize
    config: Dict[str, Any]
    visible: bool = True
    rotation: float = 0  # Rotation in degrees

class VideoTransform(BaseModel):
    x: float = 0
    y: float = 0
    scale: float = 1.0
    rotation: float = 0

class ApiConfigs(BaseModel):
    weather_api_key: Optional[str] = ""
    transit_stop_id: Optional[str] = ""
    timezone: Optional[str] = "America/Los_Angeles"

class OverlayConfigBase(BaseModel):
    name: str
    background_type: str = "video"
    video_id: Optional[int] = None
    mapping_scene_id: Optional[int] = None
    video_transform: VideoTransform
    widgets: List[Widget]
    api_configs: ApiConfigs

class OverlayConfigCreate(OverlayConfigBase):
    pass

class OverlayConfigUpdate(BaseModel):
    name: Optional[str] = None
    background_type: Optional[str] = None
    video_id: Optional[int] = None
    mapping_scene_id: Optional[int] = None
    video_transform: Optional[VideoTransform] = None
    widgets: Optional[List[Widget]] = None
    api_configs: Optional[ApiConfigs] = None

class OverlayConfigResponse(OverlayConfigBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

class OverlayStreamRequest(BaseModel):
    video_id: Optional[int] = None
    config_id: Optional[int] = None

class OverlayStreamResponse(BaseModel):
    background_type: str = "video"
    streaming_url: Optional[str] = None
    port: int = 0
    video_path: Optional[str] = None
    config_id: Optional[int] = None
    mapping_scene: Optional[Dict[str, Any]] = None


class OverlayWindowInitResponse(BaseModel):
    config: OverlayConfigResponse
    background_type: str = "video"
    streaming_url: Optional[str] = None
    video_path: Optional[str] = None
    mapping_scene: Optional[Dict[str, Any]] = None


class OverlayCastStartRequest(BaseModel):
    device_id: str
    config_id: int
    overlay_base_url: Optional[str] = None
    controls_hidden: bool = True
    viewport_width: int = 1280
    viewport_height: int = 720
    capture_width: int = 1280
    capture_height: int = 720
    quality: int = 50
    frame_rate: int = 20
    stream_port: Optional[int] = None


class OverlayCastSessionResponse(BaseModel):
    session_id: str
    device_id: str
    config_id: int
    overlay_url: str
    relay_url: str
    stream_port: int
    status: str
    archived: bool
    current_step: str
    debug_log: List[str]
    active_clients: int
    ffmpeg_speed: Optional[float] = None
    ffmpeg_fps: Optional[float] = None
    ffmpeg_bitrate_kbps: Optional[float] = None
    encoder: Optional[str] = None
    last_client_connected_at: Optional[datetime] = None
    last_client_disconnected_at: Optional[datetime] = None
    last_client_activity_at: Optional[datetime] = None
    started_at: datetime
    updated_at: datetime
    error: Optional[str] = None
    discovery_session_id: Optional[str] = None
