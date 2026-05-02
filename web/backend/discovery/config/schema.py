"""
Configuration schemas for validation and type safety.
"""

from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, time
from enum import Enum


class CastingMethodEnum(str, Enum):
    """Supported casting methods"""
    DLNA = "dlna"
    AIRPLAY = "airplay"
    OVERLAY = "overlay"
    CHROMECAST = "chromecast"
    MIRACAST = "miracast"


class ContentType(str, Enum):
    """Supported content types"""
    VIDEO = "video/mp4"
    AUDIO = "audio/mp3"
    IMAGE = "image/jpeg"
    WEB = "text/html"
    STREAM = "application/x-mpegURL"


class RetryPolicy(BaseModel):
    """Retry policy configuration"""
    max_attempts: int = Field(default=3, ge=1, le=10)
    delay_seconds: int = Field(default=5, ge=1, le=300)
    backoff_multiplier: float = Field(default=2.0, ge=1.0, le=5.0)


class HealthCheckConfig(BaseModel):
    """Health check configuration"""
    enabled: bool = True
    interval_seconds: int = Field(default=30, ge=10, le=300)
    timeout_seconds: int = Field(default=5, ge=1, le=30)


class ScheduleConfig(BaseModel):
    """Schedule configuration for content casting"""
    enabled: bool = True
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    days_of_week: List[int] = Field(default_factory=lambda: list(range(7)))  # 0=Monday, 6=Sunday
    timezone: str = "UTC"
    
    @field_validator('days_of_week')
    @classmethod
    def validate_days(cls, v):
        if not all(0 <= day <= 6 for day in v):
            raise ValueError('Days must be between 0 (Monday) and 6 (Sunday)')
        return v


class ContentConfig(BaseModel):
    """Content configuration"""
    url: str
    type: ContentType = ContentType.VIDEO
    duration: Optional[int] = None  # Duration in seconds
    loop: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)


class DeviceConfig(BaseModel):
    """Device-specific configuration"""
    name: str
    casting_method: CastingMethodEnum
    content: ContentConfig
    priority: int = Field(default=50, ge=0, le=100)
    schedule: Optional[ScheduleConfig] = None
    group: Optional[str] = None
    zone: Optional[str] = None
    auto_cast: bool = True
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # DLNA specific
    action_url: Optional[str] = None
    
    # AirPlay specific
    airplay_password: Optional[str] = None
    
    # Overlay specific
    display_index: Optional[int] = None
    overlay_config_id: Optional[int] = None
    widgets: Optional[List[Dict[str, Any]]] = None


class GlobalConfig(BaseModel):
    """Global configuration settings"""
    discovery_interval: int = Field(default=10, ge=5, le=300)
    auto_cast: bool = True
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)
    log_level: str = "INFO"
    api_port: int = Field(default=8000, ge=1024, le=65535)
    web_ui_enabled: bool = True
    
    # Discovery backend settings
    backends: Dict[str, bool] = Field(default_factory=lambda: {
        "dlna": True,
        "airplay": True,
        "overlay": True,
        "chromecast": False,
        "miracast": False
    })
    
    # Performance settings
    max_concurrent_streams: int = Field(default=10, ge=1, le=100)
    stream_buffer_size: int = Field(default=1048576, ge=65536)  # 1MB default
    
    # Security settings
    auth_enabled: bool = False
    api_key: Optional[str] = None
    allowed_origins: List[str] = Field(default_factory=lambda: ["*"])


class ConfigurationFile(BaseModel):
    """Complete configuration file structure"""
    version: str = "1.0"
    global_config: GlobalConfig = Field(default_factory=GlobalConfig)
    devices: List[DeviceConfig] = Field(default_factory=list)
    groups: Dict[str, List[str]] = Field(default_factory=dict)  # group_name -> device_names
    zones: Dict[str, Dict[str, Any]] = Field(default_factory=dict)  # zone_name -> zone_config
    
    def validate_groups(self):
        """Validate that all devices in groups exist"""
        device_names = {d.name for d in self.devices}
        for group_name, group_devices in self.groups.items():
            for device_name in group_devices:
                if device_name not in device_names:
                    raise ValueError(f"Device {device_name} in group {group_name} not found in devices")
    
    def get_devices_by_group(self, group_name: str) -> List[DeviceConfig]:
        """Get all devices in a group"""
        if group_name not in self.groups:
            return []
        
        device_names = self.groups[group_name]
        return [d for d in self.devices if d.name in device_names]
    
    def get_devices_by_zone(self, zone_name: str) -> List[DeviceConfig]:
        """Get all devices in a zone"""
        return [d for d in self.devices if d.zone == zone_name]


# Validation functions
def validate_device_config(config: Dict[str, Any]) -> Union[DeviceConfig, None]:
    """
    Validate and parse device configuration.
    
    Args:
        config: Device configuration dictionary
        
    Returns:
        DeviceConfig if valid, None otherwise
    """
    try:
        return DeviceConfig(**config)
    except Exception as e:
        logger.error(f"Invalid device configuration: {e}")
        return None


def validate_global_config(config: Dict[str, Any]) -> Union[GlobalConfig, None]:
    """
    Validate and parse global configuration.
    
    Args:
        config: Global configuration dictionary
        
    Returns:
        GlobalConfig if valid, None otherwise
    """
    try:
        return GlobalConfig(**config)
    except Exception as e:
        logger.error(f"Invalid global configuration: {e}")
        return None


def validate_configuration_file(data: Dict[str, Any]) -> Union[ConfigurationFile, None]:
    """
    Validate and parse complete configuration file.
    
    Args:
        data: Configuration file data
        
    Returns:
        ConfigurationFile if valid, None otherwise
    """
    try:
        config = ConfigurationFile(**data)
        config.validate_groups()
        return config
    except Exception as e:
        logger.error(f"Invalid configuration file: {e}")
        return None


# Example configuration
EXAMPLE_CONFIG = {
    "version": "1.0",
    "global_config": {
        "discovery_interval": 10,
        "auto_cast": True,
        "retry_policy": {
            "max_attempts": 3,
            "delay_seconds": 5,
            "backoff_multiplier": 2.0
        },
        "backends": {
            "dlna": True,
            "airplay": True,
            "overlay": True
        }
    },
    "devices": [
        {
            "name": "Living Room TV",
            "casting_method": "dlna",
            "content": {
                "url": "/path/to/video.mp4",
                "type": "video/mp4",
                "loop": True
            },
            "priority": 100,
            "group": "main_displays",
            "zone": "living_room"
        },
        {
            "name": "Kitchen Display",
            "casting_method": "overlay",
            "content": {
                "url": "http://localhost:8000/static/overlay_window.html",
                "type": "text/html"
            },
            "priority": 80,
            "group": "info_displays",
            "zone": "kitchen",
            "display_index": 1,
            "widgets": [
                {
                    "type": "weather",
                    "position": {"x": 50, "y": 50},
                    "config": {"city": "San Francisco"}
                }
            ]
        }
    ],
    "groups": {
        "main_displays": ["Living Room TV", "Bedroom TV"],
        "info_displays": ["Kitchen Display", "Office Monitor"]
    },
    "zones": {
        "living_room": {
            "description": "Main entertainment area",
            "default_volume": 70
        },
        "kitchen": {
            "description": "Kitchen information display",
            "brightness": 80
        }
    }
}


import logging
logger = logging.getLogger(__name__)