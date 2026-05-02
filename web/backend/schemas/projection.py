from pydantic import BaseModel, ConfigDict
from typing import List, Dict, Any, Optional
from datetime import datetime

class ZoneTransform(BaseModel):
    """Transform properties for a zone"""
    x: float = 0
    y: float = 0
    scale: float = 1.0
    rotation: float = 0

class ZoneAssignment(BaseModel):
    """Assignment of content to a zone"""
    type: str  # 'animation' or 'video'
    content: Optional[str] = None  # animation ID or video ID

class Zone(BaseModel):
    """Individual zone within a projection"""
    id: str
    bounds: Dict[str, float]  # x, y, width, height
    transform: ZoneTransform = ZoneTransform()
    assignment: ZoneAssignment = ZoneAssignment(type='empty')
    sourceMask: Optional[str] = None  # Which mask file this zone came from
    
class MaskData(BaseModel):
    """Mask information"""
    id: str
    name: str
    width: int
    height: int
    filepath: Optional[str] = None
    url: Optional[str] = None

class ApiConfigs(BaseModel):
    """API configurations for data sources"""
    weather_api_key: Optional[str] = ""
    transit_stop_id: Optional[str] = ""
    timezone: Optional[str] = "America/Los_Angeles"

class ProjectionConfigBase(BaseModel):
    """Base projection configuration"""
    name: str
    mask_data: MaskData
    zones: List[Zone]
    api_configs: ApiConfigs = ApiConfigs()

class ProjectionConfigCreate(ProjectionConfigBase):
    """Schema for creating a projection configuration"""
    pass

class ProjectionConfigUpdate(BaseModel):
    """Schema for updating a projection configuration"""
    name: Optional[str] = None
    zones: Optional[List[Zone]] = None
    api_configs: Optional[ApiConfigs] = None

class ProjectionConfigResponse(ProjectionConfigBase):
    """Schema for projection configuration response"""
    id: int
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)