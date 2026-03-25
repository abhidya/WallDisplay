"""
Registry for managing streaming sessions across the application.
"""
import threading
import time
import logging
import uuid
import os
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta

from .streaming_session import StreamingSession

logger = logging.getLogger(__name__)

class StreamingSessionRegistry:
    """
    Registry for managing streaming sessions, implemented as a singleton.
    """
    _instance = None
    _lock = threading.Lock()
    
    @classmethod
    def get_instance(cls):
        """
        Get the singleton instance, creating it if it doesn't exist
        
        Returns:
            StreamingSessionRegistry: The singleton instance
        """
        with cls._lock:
            if not cls._instance:
                cls._instance = StreamingSessionRegistry()
            return cls._instance
            
    def __init__(self):
        """
        Initialize the registry
        """
        self.sessions: Dict[str, StreamingSession] = {}
        self.session_lock = threading.Lock()
        self.device_sessions: Dict[str, List[str]] = {}  # Map device names to session IDs
        self.monitoring_thread = None
        self.monitoring_running = False
        self.health_check_interval = 5  # seconds
        self.health_check_handlers = []  # Functions to call during health checks
        
    def register_session(
        self,
        device_name: str,
        video_path: str,
        server_ip: str,
        server_port: int,
        stream_type: str = "device_stream",
        consumer_id: Optional[str] = None,
    ) -> StreamingSession:
        """
        Register a new streaming session
        
        Args:
            device_name: Name of the device receiving the stream
            video_path: Path to the video file being streamed
            server_ip: IP address of the streaming server
            server_port: Port of the streaming server
            
        Returns:
            StreamingSession: The newly created session
        """
        # Generate a unique session ID
        session_id = str(uuid.uuid4())
        
        # Create new session
        session = StreamingSession(
            session_id,
            device_name,
            video_path,
            server_ip,
            server_port,
            stream_type=stream_type,
            consumer_id=consumer_id,
        )
        
        # Add to registry with thread safety
        with self.session_lock:
            self.sessions[session_id] = session
            
            # Track by device
            if device_name not in self.device_sessions:
                self.device_sessions[device_name] = []
            self.device_sessions[device_name].append(session_id)
            
        logger.info(f"Registered streaming session {session_id} for device {device_name}")
        
        # Start monitoring if not already running
        self._ensure_monitoring_running()
        
        return session
        
    def unregister_session(self, session_id: str) -> bool:
        """
        Unregister a streaming session
        
        Args:
            session_id: ID of the session to unregister
            
        Returns:
            bool: True if session was found and unregistered, False otherwise
        """
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                device_name = session.device_name
                
                # Mark as inactive before removing
                session.active = False
                session.status = "completed"
                
                # Remove from registry
                del self.sessions[session_id]
                
                # Remove from device tracking
                if device_name in self.device_sessions:
                    if session_id in self.device_sessions[device_name]:
                        self.device_sessions[device_name].remove(session_id)
                    
                    # Clean up empty device entries
                    if not self.device_sessions[device_name]:
                        del self.device_sessions[device_name]
                
                logger.info(f"Unregistered streaming session {session_id} for device {device_name}")
                return True
            else:
                logger.warning(f"Session {session_id} not found, cannot unregister")
                return False
                
    def get_session(self, session_id: str) -> Optional[StreamingSession]:
        """
        Get a streaming session by ID
        
        Args:
            session_id: ID of the session to get
            
        Returns:
            Optional[StreamingSession]: The session if found, None otherwise
        """
        with self.session_lock:
            return self.sessions.get(session_id)
            
    def get_sessions_for_device(self, device_name: str) -> List[StreamingSession]:
        """
        Get all streaming sessions for a device
        
        Args:
            device_name: Name of the device
            
        Returns:
            List[StreamingSession]: List of sessions for the device
        """
        with self.session_lock:
            if device_name not in self.device_sessions:
                return []
                
            return [self.sessions[session_id] for session_id in self.device_sessions[device_name] 
                   if session_id in self.sessions]
                   
    def get_active_sessions(self) -> List[StreamingSession]:
        """
        Get all active streaming sessions
        
        Returns:
            List[StreamingSession]: List of active sessions
        """
        with self.session_lock:
            return [session for session in self.sessions.values() if session.active]
            
    def update_session_activity(self, session_id: str, client_ip: Optional[str] = None, 
                               bytes_transferred: int = 0) -> bool:
        """
        Update activity for a streaming session
        
        Args:
            session_id: ID of the session to update
            client_ip: Client IP address if available
            bytes_transferred: Number of bytes transferred
            
        Returns:
            bool: True if session was found and updated, False otherwise
        """
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.update_activity(client_ip, bytes_transferred)
                return True
            else:
                return False
                
    def record_connection_event(self, session_id: str, connected: bool) -> bool:
        """
        Record a connection event for a session
        
        Args:
            session_id: ID of the session
            connected: Whether the connection was established or dropped
            
        Returns:
            bool: True if session was found and updated, False otherwise
        """
        with self.session_lock:
            if session_id in self.sessions:
                session = self.sessions[session_id]
                session.record_connection(connected)
                return True
            else:
                return False
                
    def register_health_check_handler(self, handler) -> None:
        """
        Register a function to be called during health checks
        
        Args:
            handler: Function that takes a session and returns a healing action
        """
        if handler not in self.health_check_handlers:
            self.health_check_handlers.append(handler)

    def unregister_health_check_handler(self, handler) -> None:
        """
        Unregister a previously registered health check handler.

        Args:
            handler: Handler to remove
        """
        self.health_check_handlers = [
            existing_handler
            for existing_handler in self.health_check_handlers
            if existing_handler != handler
        ]
        
    def register_device_handler(self, device_name: str, handler) -> None:
        """
        Register a handler for a specific device
        
        This is an alias for register_health_check_handler that makes the API more clear
        when registering device-specific handlers.
        
        Args:
            device_name: Name of the device this handler is for
            handler: Function that takes a session and performs recovery actions
        """
        logger.info(f"Registering health check handler for device: {device_name}")
        # We currently don't filter by device in the health check loop,
        # but the handler itself can check if the session belongs to its device
        self.register_health_check_handler(handler)
        
    def _ensure_monitoring_running(self) -> None:
        """
        Ensure the monitoring thread is running
        """
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            return
            
        self.monitoring_running = True
        self.monitoring_thread = threading.Thread(target=self._monitoring_loop)
        self.monitoring_thread.daemon = True
        self.monitoring_thread.start()
        logger.info("Started streaming session monitoring")
        
    def stop_monitoring(self) -> None:
        """
        Stop the monitoring thread
        """
        self.monitoring_running = False
        if self.monitoring_thread and self.monitoring_thread.is_alive():
            self.monitoring_thread.join(timeout=2.0)
        logger.info("Stopped streaming session monitoring")
        
    def _monitoring_loop(self) -> None:
        """
        Background thread to monitor session health
        """
        while self.monitoring_running:
            try:
                self._check_sessions_health()
                self._clean_stale_sessions()
            except Exception as e:
                logger.error(f"Error in streaming monitoring loop: {e}")
                
            time.sleep(self.health_check_interval)
            
    def _check_sessions_health(self) -> None:
        """
        Check health of all active sessions
        """
        # Get a copy of active sessions to avoid long lock holding
        active_sessions = self.get_active_sessions()
        stalled_sessions = []
        
        for session in active_sessions:
            try:
                # Check for sessions that have been running too long (e.g., 24 hours)
                session_duration = (datetime.now() - session.start_time).total_seconds()
                max_session_duration = 86400  # 24 hours in seconds
                
                if session_duration > max_session_duration:
                    logger.warning(f"Session {session.session_id} has been running for {session_duration/3600:.1f} hours, marking as timed out")
                    session.set_error("Session timed out after 24 hours")
                    # Unregister the session
                    self.unregister_session(session.session_id)
                    continue
                
                # Check for stalled sessions
                # Increased from 15s to 90s to account for devices that buffer entire video
                if session.is_stalled(inactivity_threshold=90.0):
                    stalled_sessions.append(session)
            except Exception as e:
                logger.error(f"Error checking session health: {e}")

        if stalled_sessions:
            self._log_stalled_session_summary(stalled_sessions)
            for session in stalled_sessions:
                for handler in self.health_check_handlers:
                    try:
                        handler(session)
                    except Exception as handler_error:
                        logger.error(f"Error in health check handler: {handler_error}")

    def _log_stalled_session_summary(self, stalled_sessions: List[StreamingSession]) -> None:
        by_stream_type: Dict[str, int] = {}
        by_device: Dict[str, int] = {}

        for session in stalled_sessions:
            by_stream_type[session.stream_type] = by_stream_type.get(session.stream_type, 0) + 1
            by_device[session.device_name] = by_device.get(session.device_name, 0) + 1

        stream_summary = ", ".join(
            f"{stream_type}={count}" for stream_type, count in sorted(by_stream_type.items())
        )
        device_summary = ", ".join(
            f"{device_name}={count}"
            for device_name, count in sorted(by_device.items(), key=lambda item: (-item[1], item[0]))[:5]
        )

        logger.warning(
            "Detected %s stalled streaming sessions (%s)%s",
            len(stalled_sessions),
            stream_summary or "no stream-type data",
            f"; top devices: {device_summary}" if device_summary else "",
        )
                
    def _clean_stale_sessions(self) -> None:
        """
        Clean up stale sessions that are inactive
        """
        stale_sessions = []
        
        with self.session_lock:
            now = datetime.now()
            # Find sessions older than 1 hour that are not active
            for session_id, session in self.sessions.items():
                if not session.active and (now - session.last_activity_time) > timedelta(hours=1):
                    stale_sessions.append(session_id)
                    
        # Remove stale sessions
        for session_id in stale_sessions:
            logger.info(f"Cleaning up stale session {session_id}")
            self.unregister_session(session_id)
            
    def get_streaming_stats(self) -> Dict[str, Any]:
        """
        Get statistics about streaming activity
        
        Returns:
            Dict[str, Any]: Streaming statistics
        """
        with self.session_lock:
            total_sessions = len(self.sessions)
            active_sessions = sum(1 for session in self.sessions.values() if session.active)
            total_bytes = sum(session.bytes_served for session in self.sessions.values())
            total_errors = sum(session.connection_errors for session in self.sessions.values())
            devices_streaming = len(self.device_sessions)
            sessions_by_stream_type: Dict[str, int] = {}
            sessions_by_consumer_prefix: Dict[str, int] = {}

            for session in self.sessions.values():
                sessions_by_stream_type[session.stream_type] = sessions_by_stream_type.get(session.stream_type, 0) + 1
                consumer_prefix = (session.consumer_id or "unassigned").split(":", 1)[0]
                sessions_by_consumer_prefix[consumer_prefix] = sessions_by_consumer_prefix.get(consumer_prefix, 0) + 1
            
            return {
                "total_sessions": total_sessions,
                "active_sessions": active_sessions,
                "total_bytes_served": total_bytes,
                "total_connection_errors": total_errors,
                "devices_streaming": devices_streaming,
                "sessions_by_stream_type": sessions_by_stream_type,
                "sessions_by_consumer_prefix": sessions_by_consumer_prefix,
                "sessions_by_status": {
                    "initializing": sum(1 for s in self.sessions.values() if s.status == "initializing"),
                    "active": sum(1 for s in self.sessions.values() if s.status == "active"),
                    "stalled": sum(1 for s in self.sessions.values() if s.status == "stalled"),
                    "error": sum(1 for s in self.sessions.values() if s.status == "error"),
                    "completed": sum(1 for s in self.sessions.values() if s.status == "completed")
                }
            } 
