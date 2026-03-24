"""
Streaming session management for tracking and monitoring active streaming sessions.
"""
import threading
import time
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class StreamingSession:
    """
    Represents a single streaming session from server to client
    """
    def __init__(
        self,
        session_id: str,
        device_name: str,
        video_path: str,
        server_ip: str,
        server_port: int,
        stream_type: str = "device_stream",
        consumer_id: Optional[str] = None,
    ):
        self.session_id = session_id
        self.device_name = device_name
        self.video_path = video_path
        self.server_ip = server_ip
        self.server_port = server_port
        self.stream_type = stream_type
        self.consumer_id = consumer_id
        self.start_time = datetime.now()
        self.last_activity_time = self.start_time
        self.bytes_served = 0
        self.client_ip = None
        self.client_connections = 0
        self.connection_errors = 0
        self.active = True
        self.bandwidth_samples = []  # List of (timestamp, bytes, duration) tuples
        self.connection_history = []  # List of (timestamp, status) tuples
        self.status = "initializing"  # One of: initializing, active, stalled, error, completed
        self.error_message = None
        self.reconnection_attempts = 0  # Track reconnection attempts
        self.last_reconnection_attempt = None  # Track when we last attempted reconnection
        self.max_reconnection_attempts = 5  # Maximum reconnection attempts before giving up
        
    def update_activity(self, client_ip: Optional[str] = None, bytes_transferred: int = 0) -> None:
        """
        Update session activity with new data
        
        Args:
            client_ip: Client IP address if available
            bytes_transferred: Number of bytes transferred in this update
        """
        self.last_activity_time = datetime.now()
        if client_ip:
            self.client_ip = client_ip
        self.bytes_served += bytes_transferred
        
        # Track bandwidth for this update
        if bytes_transferred > 0:
            now = time.time()
            if len(self.bandwidth_samples) > 0:
                last_time = self.bandwidth_samples[-1][0]
                duration = now - last_time
                if duration > 0:
                    self.bandwidth_samples.append((now, bytes_transferred, duration))
                    # Keep only the last 10 samples
                    if len(self.bandwidth_samples) > 10:
                        self.bandwidth_samples.pop(0)
            else:
                self.bandwidth_samples.append((now, bytes_transferred, 0))
                
    def record_connection(self, connected: bool) -> None:
        """
        Record a connection event
        
        Args:
            connected: Whether the connection was established or dropped
        """
        if connected:
            self.client_connections += 1
            self.status = "active"
        else:
            self.connection_errors += 1
            if self.status == "active":
                self.status = "stalled"
                
        # Record in history
        self.connection_history.append((datetime.now(), "connected" if connected else "disconnected"))
        # Keep only the last 20 connection events
        if len(self.connection_history) > 20:
            self.connection_history.pop(0)
            
    def set_error(self, message: str) -> None:
        """
        Set an error state for this session
        
        Args:
            message: Error message
        """
        self.status = "error"
        self.error_message = message
        self.active = False
        
    def complete(self) -> None:
        """
        Mark this session as completed successfully
        """
        self.status = "completed"
        self.active = False
        
    def get_bandwidth(self) -> float:
        """
        Calculate current bandwidth in bytes/second
        
        Returns:
            float: Current bandwidth in bytes/second or 0 if not enough data
        """
        if len(self.bandwidth_samples) < 2:
            return 0
            
        # Calculate average from samples
        total_bytes = sum(sample[1] for sample in self.bandwidth_samples)
        total_duration = sum(sample[2] for sample in self.bandwidth_samples)
        
        if total_duration > 0:
            return total_bytes / total_duration
        else:
            return 0
            
    def is_stalled(self, inactivity_threshold: float = 10.0) -> bool:
        """
        Check if this session appears to be stalled
        
        Args:
            inactivity_threshold: Threshold in seconds for considering a session stalled
            
        Returns:
            bool: True if the session appears stalled, False otherwise
        """
        if not self.active:
            return False
            
        if self.status == "error":
            return True
            
        # Check time since last activity
        time_since_activity = (datetime.now() - self.last_activity_time).total_seconds()
        return time_since_activity > inactivity_threshold
        
    def record_reconnection_attempt(self) -> None:
        """
        Record that a reconnection attempt was made
        """
        self.reconnection_attempts += 1
        self.last_reconnection_attempt = datetime.now()
        
    def has_exceeded_reconnection_limit(self) -> bool:
        """
        Check if the session has exceeded the maximum reconnection attempts
        
        Returns:
            bool: True if exceeded, False otherwise
        """
        return self.reconnection_attempts >= self.max_reconnection_attempts
        
    def should_attempt_reconnection(self) -> bool:
        """
        Check if we should attempt to reconnect this session
        
        Returns:
            bool: True if we should attempt reconnection, False otherwise
        """
        # Don't reconnect if we've exceeded the limit
        if self.has_exceeded_reconnection_limit():
            return False
            
        # Don't reconnect if we just tried recently (within 30 seconds)
        if self.last_reconnection_attempt:
            time_since_last_attempt = (datetime.now() - self.last_reconnection_attempt).total_seconds()
            if time_since_last_attempt < 30:
                return False
                
        return True
        
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert session to dictionary for API responses
        
        Returns:
            Dict[str, Any]: Session information as a dictionary
        """
        return {
            "session_id": self.session_id,
            "device_name": self.device_name,
            "stream_type": self.stream_type,
            "consumer_id": self.consumer_id,
            "video_path": self.video_path,
            "server_ip": self.server_ip,
            "server_port": self.server_port,
            "start_time": self.start_time.isoformat(),
            "last_activity": self.last_activity_time.isoformat(),
            "bytes_served": self.bytes_served,
            "client_ip": self.client_ip,
            "connection_count": self.client_connections,
            "error_count": self.connection_errors,
            "status": self.status,
            "active": self.active,
            "bandwidth_bps": self.get_bandwidth(),
            "duration_seconds": (datetime.now() - self.start_time).total_seconds(),
            "error_message": self.error_message,
            "reconnection_attempts": self.reconnection_attempts
        } 
