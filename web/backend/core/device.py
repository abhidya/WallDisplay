from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any
import logging
import threading

logger = logging.getLogger(__name__)

class Device(ABC):
    """
    Abstract base class for all device types (DLNA, Transcreen, etc.)
    """
    def __init__(self, device_info: Dict[str, Any]):
        self.device_info = device_info
        self.name = device_info.get("device_name", "Unknown Device")
        self.type = device_info.get("type", "unknown")
        self.status = "disconnected"
        self.current_video = None
        self.is_playing = False
        self.streaming_url = None
        self.streaming_port = None
        self.device_manager = None
        self._lock = threading.Lock()  # Lock for thread-safe status updates

    def update_status(self, status: str) -> None:
        """
        Update the device status
        
        Args:
            status: New status for the device
        """
        with self._lock:
            self.status = status
            logger.info(f"Device {self.name} status updated to {status}")
            
    def update_playing(self, is_playing: bool) -> None:
        """
        Update the device playing state
        
        Args:
            is_playing: Whether the device is playing
        """
        with self._lock:
            self.is_playing = is_playing
            logger.info(f"Device {self.name} playing state updated to {is_playing}")
            
    def update_video(self, video_path: str) -> None:
        """
        Update the current video
        
        Args:
            video_path: Path to the current video
        """
        with self._lock:
            self.current_video = video_path
            logger.info(f"Device {self.name} current video updated to {video_path}")
            
    def update_streaming_info(self, streaming_url: Optional[str], streaming_port: Optional[int]) -> None:
        """
        Update the streaming URL and port for this device
        
        Args:
            streaming_url: URL of the streaming server
            streaming_port: Port of the streaming server
        """
        with self._lock:
            self.streaming_url = streaming_url
            self.streaming_port = streaming_port
            logger.info(f"Device {self.name} streaming info updated: {streaming_url} on port {streaming_port}")
            
    @abstractmethod
    def play(self, video_url: str, loop: bool = False) -> bool:
        """
        Play a video on the device
        
        Args:
            video_url: URL of the video to play
            loop: Whether to loop the video
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def stop(self) -> bool:
        """
        Stop playback on the device
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
        
    @abstractmethod
    def pause(self) -> bool:
        """
        Pause playback on the device
        
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def seek(self, position: str) -> bool:
        """
        Seek to a position in the current video
        
        Args:
            position: Position to seek to (format: HH:MM:SS)
            
        Returns:
            bool: True if successful, False otherwise
        """
        pass
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert device to dictionary representation
        
        Returns:
            Dict[str, Any]: Dictionary representation of the device
        """
        return {
            "name": self.name,
            "type": self.type,
            "status": self.status,
            "current_video": self.current_video,
            "is_playing": self.is_playing,
            "streaming_url": self.streaming_url,
            "streaming_port": self.streaming_port,
            **self.device_info
        }
