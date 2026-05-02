from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List
from datetime import datetime

class VideoBase(BaseModel):
    """
    Base schema for a video
    """
    name: str = Field(..., description="Video name")
    path: str = Field(..., description="Path to the video file")
    category: str = Field("background", description="Category for organizing media")
    source_type: str = Field("upload", description="How the media was added")
    source_directory_id: Optional[int] = Field(None, description="Directory source identifier")

class VideoCreate(VideoBase):
    """
    Schema for creating a video
    """
    file_name: Optional[str] = Field(None, description="Video file name")
    file_size: Optional[int] = Field(None, description="Video file size in bytes")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    format: Optional[str] = Field(None, description="Video format")
    resolution: Optional[str] = Field(None, description="Video resolution")
    preprocessing_status: Optional[str] = Field("pending", description="Preprocessing queue status")
    preprocessing_error: Optional[str] = Field(None, description="Preprocessing failure detail")
    overlay_optimized: Optional[bool] = Field(False, description="Whether the file was normalized for overlay playback")
    has_subtitle: Optional[bool] = Field(False, description="Whether the video has subtitles")
    subtitle_path: Optional[str] = Field(None, description="Path to the subtitle file")

class VideoUpdate(BaseModel):
    """
    Schema for updating a video
    """
    name: Optional[str] = Field(None, description="Video name")
    path: Optional[str] = Field(None, description="Path to the video file")
    file_name: Optional[str] = Field(None, description="Video file name")
    file_size: Optional[int] = Field(None, description="Video file size in bytes")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    format: Optional[str] = Field(None, description="Video format")
    resolution: Optional[str] = Field(None, description="Video resolution")
    category: Optional[str] = Field(None, description="Category for organizing media")
    source_type: Optional[str] = Field(None, description="How the media was added")
    source_directory_id: Optional[int] = Field(None, description="Directory source identifier")
    preprocessing_status: Optional[str] = Field(None, description="Preprocessing queue status")
    preprocessing_error: Optional[str] = Field(None, description="Preprocessing failure detail")
    overlay_optimized: Optional[bool] = Field(None, description="Whether the file was normalized for overlay playback")
    has_subtitle: Optional[bool] = Field(None, description="Whether the video has subtitles")
    subtitle_path: Optional[str] = Field(None, description="Path to the subtitle file")

class VideoResponse(VideoBase):
    """
    Schema for video response
    """
    id: int = Field(..., description="Video ID")
    file_name: Optional[str] = Field(None, description="Video file name")
    file_size: Optional[int] = Field(None, description="Video file size in bytes")
    duration: Optional[float] = Field(None, description="Video duration in seconds")
    format: Optional[str] = Field(None, description="Video format")
    resolution: Optional[str] = Field(None, description="Video resolution")
    category: str = Field("background", description="Category for organizing media")
    source_type: str = Field("upload", description="How the media was added")
    source_directory_id: Optional[int] = Field(None, description="Directory source identifier")
    preprocessing_status: str = Field("pending", description="Preprocessing queue status")
    preprocessing_error: Optional[str] = Field(None, description="Preprocessing failure detail")
    overlay_optimized: bool = Field(False, description="Whether the file was normalized for overlay playback")
    has_subtitle: bool = Field(False, description="Whether the video has subtitles")
    subtitle_path: Optional[str] = Field(None, description="Path to the subtitle file")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    model_config = ConfigDict(from_attributes=True)

class VideoList(BaseModel):
    """
    Schema for a list of videos
    """
    videos: List[VideoResponse] = Field(..., description="List of videos")
    total: int = Field(..., description="Total number of videos")

class VideoUploadResponse(BaseModel):
    """
    Schema for video upload response
    """
    success: bool = Field(..., description="Whether the upload was successful")
    message: str = Field(..., description="Response message")
    video: Optional[VideoResponse] = Field(None, description="Uploaded video")
