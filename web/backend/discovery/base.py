"""
Base classes and interfaces for the unified discovery system.
"""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import asyncio
import logging

logger = logging.getLogger(__name__)


class CastingMethod(Enum):
    """Supported casting methods"""
    DLNA = "dlna"
    AIRPLAY = "airplay"
    OVERLAY = "overlay"
    CHROMECAST = "chromecast"
    MIRACAST = "miracast"


class DeviceCapability(Enum):
    """Device capabilities"""
    VIDEO_PLAYBACK = "video_playback"
    AUDIO_PLAYBACK = "audio_playback"
    IMAGE_DISPLAY = "image_display"
    WEB_CONTENT = "web_content"
    SCREEN_MIRRORING = "screen_mirroring"
    VOLUME_CONTROL = "volume_control"
    SEEK_CONTROL = "seek_control"


@dataclass
class Device:
    """Unified device representation"""
    id: str
    name: str
    friendly_name: str
    casting_method: CastingMethod
    hostname: str
    port: int
    capabilities: List[DeviceCapability] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    discovered_at: datetime = field(default_factory=datetime.now)
    last_seen: datetime = field(default_factory=datetime.now)
    is_online: bool = True
    
    # DLNA specific fields (optional)
    action_url: Optional[str] = None
    location: Optional[str] = None
    manufacturer: Optional[str] = None
    
    # AirPlay specific fields (optional)
    features: Optional[int] = None
    model: Optional[str] = None
    
    # Overlay specific fields (optional)
    display_index: Optional[int] = None
    resolution: Optional[tuple] = None
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        if isinstance(other, Device):
            return self.id == other.id
        return False
    
    def update_last_seen(self):
        """Update the last seen timestamp"""
        self.last_seen = datetime.now()
        
    def has_capability(self, capability: DeviceCapability) -> bool:
        """Check if device has a specific capability"""
        return capability in self.capabilities

    def to_dict(self) -> Dict[str, Any]:
        """Convert device to a JSON-serializable dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "friendly_name": self.friendly_name,
            "casting_method": self.casting_method.value,
            "hostname": self.hostname,
            "port": self.port,
            "capabilities": [capability.value for capability in self.capabilities],
            "metadata": self.metadata,
            "discovered_at": self.discovered_at.isoformat(),
            "last_seen": self.last_seen.isoformat(),
            "is_online": self.is_online,
            "action_url": self.action_url,
            "location": self.location,
            "manufacturer": self.manufacturer,
            "features": self.features,
            "model": self.model,
            "display_index": self.display_index,
            "resolution": list(self.resolution) if self.resolution else None,
        }


@dataclass
class CastingSession:
    """Represents an active casting session"""
    id: str
    device: Device
    content_url: str
    content_type: str
    started_at: datetime = field(default_factory=datetime.now)
    is_active: bool = True
    is_paused: bool = False
    position: float = 0.0  # seconds
    duration: float = 0.0  # seconds
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert casting session to a JSON-serializable dictionary."""
        return {
            "session_id": self.id,
            "device_id": self.device.id,
            "device_name": self.device.friendly_name,
            "content_url": self.content_url,
            "content_type": self.content_type,
            "started_at": self.started_at.isoformat(),
            "is_active": self.is_active,
            "is_paused": self.is_paused,
            "position": self.position,
            "duration": self.duration,
            "metadata": self.metadata,
        }


class DiscoveryBackend(ABC):
    """Abstract base class for discovery backends"""
    
    def __init__(self, name: str, casting_method: CastingMethod):
        self.name = name
        self.casting_method = casting_method
        self.discovered_devices: Dict[str, Device] = {}
        self.active_sessions: Dict[str, CastingSession] = {}
        self.discovery_running = False
        self.discovery_interval = 10  # seconds
        self._discovery_task: Optional[asyncio.Task] = None
        self._callbacks: List[Callable] = []
        
    @abstractmethod
    async def discover_devices(self) -> List[Device]:
        """
        Discover devices using this backend's protocol.
        
        Returns:
            List of discovered devices
        """
        pass
    
    @abstractmethod
    async def cast_content(self, device: Device, content_url: str, 
                          content_type: str = "video/mp4", 
                          metadata: Optional[Dict[str, Any]] = None) -> CastingSession:
        """
        Cast content to a device.
        
        Args:
            device: Target device
            content_url: URL of content to cast
            content_type: MIME type of content
            metadata: Additional metadata
            
        Returns:
            CastingSession object
        """
        pass
    
    @abstractmethod
    async def stop_casting(self, session: CastingSession) -> bool:
        """
        Stop an active casting session.
        
        Args:
            session: Session to stop
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def pause_casting(self, session: CastingSession) -> bool:
        """
        Pause an active casting session.
        
        Args:
            session: Session to pause
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def resume_casting(self, session: CastingSession) -> bool:
        """
        Resume a paused casting session.
        
        Args:
            session: Session to resume
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def seek(self, session: CastingSession, position: float) -> bool:
        """
        Seek to a position in the content.
        
        Args:
            session: Active session
            position: Position in seconds
            
        Returns:
            True if successful
        """
        pass
    
    @abstractmethod
    async def get_status(self, session: CastingSession) -> Dict[str, Any]:
        """
        Get current status of a casting session.
        
        Args:
            session: Session to query
            
        Returns:
            Status dictionary
        """
        pass
    
    def supports_device(self, device: Device) -> bool:
        """
        Check if this backend supports a device.
        
        Args:
            device: Device to check
            
        Returns:
            True if supported
        """
        return device.casting_method == self.casting_method
    
    def supports_capability(self, capability: DeviceCapability) -> bool:
        """
        Check if this backend supports a capability.
        
        Override in subclasses to specify supported capabilities.
        
        Args:
            capability: Capability to check
            
        Returns:
            True if supported
        """
        return True
    
    async def start_discovery(self):
        """Start continuous device discovery"""
        if self.discovery_running:
            logger.warning(f"{self.name} discovery already running")
            return
            
        self.discovery_running = True
        self._discovery_task = asyncio.create_task(self._discovery_loop())
        logger.info(f"Started {self.name} discovery")
        
    async def stop_discovery(self):
        """Stop device discovery"""
        self.discovery_running = False
        if self._discovery_task:
            self._discovery_task.cancel()
            try:
                await self._discovery_task
            except asyncio.CancelledError:
                pass
        logger.info(f"Stopped {self.name} discovery")
        
    async def _discovery_loop(self):
        """Continuous discovery loop"""
        while self.discovery_running:
            try:
                devices = await self.discover_devices()
                
                # Update discovered devices
                current_device_ids = set()
                for device in devices:
                    current_device_ids.add(device.id)
                    
                    # Update existing or add new device
                    if device.id in self.discovered_devices:
                        self.discovered_devices[device.id].update_last_seen()
                    else:
                        self.discovered_devices[device.id] = device
                        await self._notify_device_discovered(device)
                
                # Mark offline devices
                for device_id, device in self.discovered_devices.items():
                    if device_id not in current_device_ids:
                        if device.is_online:
                            device.is_online = False
                            await self._notify_device_lost(device)
                            
            except Exception as e:
                logger.error(f"Error in {self.name} discovery loop: {e}")
                
            await asyncio.sleep(self.discovery_interval)
    
    def register_callback(self, callback: Callable):
        """Register a callback for device events"""
        self._callbacks.append(callback)
        
    async def _notify_device_discovered(self, device: Device):
        """Notify callbacks of newly discovered device"""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('device_discovered', device)
                else:
                    callback('device_discovered', device)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")
                
    async def _notify_device_lost(self, device: Device):
        """Notify callbacks of lost device"""
        for callback in self._callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback('device_lost', device)
                else:
                    callback('device_lost', device)
            except Exception as e:
                logger.error(f"Error in discovery callback: {e}")
                
    def get_discovered_devices(self) -> List[Device]:
        """Get all discovered devices"""
        return list(self.discovered_devices.values())
    
    def get_online_devices(self) -> List[Device]:
        """Get online devices"""
        return [d for d in self.discovered_devices.values() if d.is_online]
    
    def get_device_by_id(self, device_id: str) -> Optional[Device]:
        """Get device by ID"""
        return self.discovered_devices.get(device_id)
    
    def get_active_sessions(self) -> List[CastingSession]:
        """Get all active casting sessions"""
        return [s for s in self.active_sessions.values() if s.is_active]
