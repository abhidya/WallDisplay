from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime

class DeviceBase(BaseModel):
    """
    Base schema for a device
    """
    name: str = Field(..., description="Device name")
    type: str = Field(..., description="Device type (dlna, transcreen, hdmi, airplay, or overlay)")
    hostname: str = Field(..., description="Device hostname or IP address")
    friendly_name: str = Field(..., description="User-friendly device name")

class DeviceCreate(DeviceBase):
    """
    Schema for creating a device
    """
    action_url: Optional[str] = Field(None, description="Action URL for DLNA devices")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    location: Optional[str] = Field(None, description="Device location URL")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional device configuration")

class DeviceUpdate(BaseModel):
    """
    Schema for updating a device
    """
    name: Optional[str] = Field(None, description="Device name")
    type: Optional[str] = Field(None, description="Device type (dlna, transcreen, hdmi, airplay, or overlay)")
    hostname: Optional[str] = Field(None, description="Device hostname or IP address")
    friendly_name: Optional[str] = Field(None, description="User-friendly device name")
    action_url: Optional[str] = Field(None, description="Action URL for DLNA devices")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    location: Optional[str] = Field(None, description="Device location URL")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional device configuration")

class DeviceResponse(DeviceBase):
    """
    Schema for device response
    """
    id: int = Field(..., description="Device ID")
    action_url: Optional[str] = Field(None, description="Action URL for DLNA devices")
    manufacturer: Optional[str] = Field(None, description="Device manufacturer")
    location: Optional[str] = Field(None, description="Device location URL")
    status: str = Field(..., description="Device status")
    is_playing: bool = Field(..., description="Whether the device is playing")
    current_video: Optional[str] = Field(None, description="Path to the current video")
    playback_position: Optional[str] = Field(None, description="Current playback position (HH:MM:SS)")
    playback_duration: Optional[str] = Field(None, description="Total video duration (HH:MM:SS)")
    playback_progress: Optional[float] = Field(None, description="Playback progress as a percentage (0-100)")
    config: Optional[Dict[str, Any]] = Field(None, description="Additional device configuration")
    streaming_url: Optional[str] = Field(None, description="Active streaming URL")
    streaming_port: Optional[int] = Field(None, description="Active streaming port")
    created_at: datetime = Field(..., description="Creation timestamp")
    updated_at: Optional[datetime] = Field(None, description="Last update timestamp")
    playback_started_at: Optional[datetime] = Field(None, description="When playback started")
    availability: Optional[str] = Field(None, description="Derived availability state")
    derived_status: Optional[str] = Field(None, description="Presentation-friendly derived status")
    manager_status: Optional[str] = Field(None, description="Raw manager status")
    manager_is_playing: Optional[bool] = Field(None, description="Whether the manager thinks the device is playing")
    seconds_since_seen: Optional[float] = Field(None, description="Seconds since the device was last seen")
    connected_since: Optional[float] = Field(None, description="Unix timestamp for the current connected period")
    uptime_seconds: Optional[float] = Field(None, description="Current connected uptime in seconds")
    downtime_started_at: Optional[float] = Field(None, description="Unix timestamp when downtime started")
    downtime_seconds: Optional[float] = Field(None, description="Current downtime in seconds")
    last_seen_at: Optional[float] = Field(None, description="Unix timestamp when the device was last seen online")
    last_lost_at: Optional[float] = Field(None, description="Unix timestamp when the device was last observed as lost")
    reconnect_count: Optional[int] = Field(None, description="Number of reconnect transitions observed")
    degraded_count: Optional[int] = Field(None, description="Number of degraded transitions observed")
    offline_count: Optional[int] = Field(None, description="Number of offline transitions observed")
    active_overlay_cast: Optional[bool] = Field(None, description="Whether an overlay cast session is active for this device")
    overlay_cast_status: Optional[str] = Field(None, description="Current overlay cast status")
    overlay_cast_started_at: Optional[datetime] = Field(None, description="When the current overlay cast session started")
    overlay_cast_uptime_seconds: Optional[float] = Field(None, description="Overlay cast session uptime in seconds")
    overlay_cast_current_step: Optional[str] = Field(None, description="Current overlay cast pipeline step")
    overlay_cast_ffmpeg_speed: Optional[float] = Field(None, description="Current FFmpeg speed multiplier for overlay cast")
    overlay_cast_ffmpeg_fps: Optional[float] = Field(None, description="Current FFmpeg FPS for overlay cast")
    overlay_cast_ffmpeg_bitrate_kbps: Optional[float] = Field(None, description="Current FFmpeg bitrate for overlay cast")
    overlay_cast_active_clients: Optional[int] = Field(None, description="Number of active relay clients for overlay cast")
    overlay_cast_session_id: Optional[str] = Field(None, description="Active overlay cast session ID")
    casting_method: Optional[str] = Field(None, description="Unified casting method")
    renderer_projector_id: Optional[str] = Field(None, description="Renderer projector ID for HDMI devices")
    hdmi_target_name: Optional[str] = Field(None, description="Selected HDMI display target")
    hdmi_connection_state: Optional[str] = Field(None, description="HDMI connection state")
    hdmi_projection_state: Optional[str] = Field(None, description="HDMI projection state")
    hdmi_power_state: Optional[str] = Field(None, description="Manually observed HDMI power state")
    hdmi_display: Optional[Dict[str, Any]] = Field(None, description="Attached HDMI display metadata")
    
    model_config = {"from_attributes": True}

class DeviceList(BaseModel):
    """
    Schema for a list of devices
    """
    devices: List[DeviceResponse] = Field(..., description="List of devices")
    total: int = Field(..., description="Total number of devices")

class DevicePlayRequest(BaseModel):
    """
    Schema for playing a video on a device
    """
    video_id: int = Field(..., description="ID of the video to play")
    loop: bool = Field(False, description="Whether to loop the video")

class DeviceActionResponse(BaseModel):
    """
    Schema for device action response
    """
    success: bool = Field(..., description="Whether the action was successful")
    message: str = Field(..., description="Response message")
