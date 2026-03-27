from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class PhotoBase(BaseModel):
    name: str = Field(..., description="Photo name")
    path: str = Field(..., description="Path to the photo file")
    category: str = Field("background", description="Category for organizing photos")
    source_type: str = Field("upload", description="How the photo was added")
    source_directory_id: Optional[int] = Field(None, description="Directory source identifier")


class PhotoCreate(PhotoBase):
    file_name: Optional[str] = Field(None, description="Photo file name")
    file_size: Optional[int] = Field(None, description="Photo file size in bytes")
    format: Optional[str] = Field(None, description="Photo format")
    resolution: Optional[str] = Field(None, description="Photo resolution")


class PhotoUpdate(BaseModel):
    name: Optional[str] = None
    path: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    resolution: Optional[str] = None
    category: Optional[str] = None
    source_type: Optional[str] = None
    source_directory_id: Optional[int] = None


class PhotoResponse(PhotoBase):
    id: int
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    format: Optional[str] = None
    resolution: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class PhotoListResponseEnvelope(BaseModel):
    photos: List[PhotoResponse]
    total: int


class PhotoUploadResponse(BaseModel):
    success: bool
    message: str
    photo: Optional[PhotoResponse] = None
