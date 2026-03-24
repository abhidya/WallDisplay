import logging
import os
import json
import traceback
import time
from typing import List, Optional, Dict, Any
from urllib.parse import urlparse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from fastapi import Depends
from datetime import datetime, timezone

from models.device import DeviceModel
from core.device_manager import DeviceManager, get_device_manager
from core.dlna_device import DLNADevice
from core.transcreen_device import TranscreenDevice
from schemas.device import DeviceCreate, DeviceUpdate
from core.config_service import ConfigService
from services.overlay_cast_service import get_overlay_cast_service

logger = logging.getLogger(__name__)

class DeviceService:
    """
    Service for managing devices
    """
    def __init__(self, db: Session, device_manager: DeviceManager):
        self.db = db
        self.device_manager = device_manager
    
    def get_devices(self, skip: int = 0, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get all devices
        
        Args:
            skip: Number of devices to skip
            limit: Maximum number of devices to return
            
        Returns:
            List[Dict[str, Any]]: List of devices as dictionaries
        """
        devices = self.db.query(DeviceModel).offset(skip).limit(limit).all()
        result = [self._device_to_dict(device) for device in devices]
        return result
    
    def get_device_by_id(self, device_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a device by ID
        
        Args:
            device_id: ID of the device
            
        Returns:
            Optional[Dict[str, Any]]: Device information
        """
        device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not device:
            return None
            
        # Convert to dictionary
        device_dict = self._device_to_dict(device)
        
        # Get the core device
        core_device = self.device_manager.get_device(device.name)
        if core_device:
            # Update with real-time information
            device_dict["is_playing"] = core_device.is_playing
            device_dict["current_video"] = core_device.current_video
        
        # Get device status
        with self.device_manager.device_state_lock:
            if device.name in self.device_manager.device_status:
                status_info = self.device_manager.device_status[device.name]
                device_dict["status"] = status_info.get("status", "unknown") # Keep this part
                device_dict["last_seen"] = status_info.get("last_seen", None)
                device_dict["connected_since"] = status_info.get("connected_since", None)
                
                # Include streaming information if available
                if "active_streaming_sessions" in status_info:
                    device_dict["active_streaming_sessions"] = status_info["active_streaming_sessions"]
                if "streaming_issues" in status_info:
                    device_dict["streaming_issues"] = status_info["streaming_issues"]
                if "streaming_bytes" in status_info:
                    device_dict["streaming_bytes"] = status_info["streaming_bytes"]
                if "streaming_bandwidth_bps" in status_info:
                    device_dict["streaming_bandwidth_bps"] = status_info["streaming_bandwidth_bps"]
                if "last_streaming_issue" in status_info:
                    device_dict["last_streaming_issue"] = status_info["last_streaming_issue"]
            # If device.name not in self.device_manager.device_status, device_dict["status"] remains as set by _device_to_dict (from db_device.status)
        
        # Get streaming session info from the registry
        try:
            from core.streaming_registry import StreamingSessionRegistry
            registry = StreamingSessionRegistry.get_instance()
            
            sessions = registry.get_sessions_for_device(device.name)
            if sessions:
                # Add summary information
                device_dict["streaming_sessions"] = len(sessions)
                device_dict["streaming_session_ids"] = [session.session_id for session in sessions]
                
                # Add detailed info from the most recent active session
                active_sessions = [s for s in sessions if s.active]
                if active_sessions:
                    latest_session = max(active_sessions, key=lambda s: s.last_activity_time)
                    device_dict["streaming_details"] = {
                        "session_id": latest_session.session_id,
                        "video_path": latest_session.video_path,
                        "server_ip": latest_session.server_ip,
                        "server_port": latest_session.server_port,
                        "bytes_served": latest_session.bytes_served,
                        "client_ip": latest_session.client_ip,
                        "connection_count": latest_session.client_connections,
                        "error_count": latest_session.connection_errors,
                        "status": latest_session.status,
                        "bandwidth_bps": latest_session.get_bandwidth(),
                        "last_activity": latest_session.last_activity_time.isoformat(),
                    }
        except (ImportError, Exception) as e:
            logger.warning(f"Error getting streaming session info: {e}")
            
        return device_dict
    
    def get_device_by_name(self, name: str) -> Optional[DeviceModel]:
        """
        Get a device by name
        
        Args:
            name: Name of the device to get
            
        Returns:
            Optional[DeviceModel]: The device if found, None otherwise
        """
        return self.db.query(DeviceModel).filter(DeviceModel.name == name).first()
    
    def create_device(self, device: DeviceCreate) -> DeviceModel:
        """
        Create a new device
        
        Args:
            device: Device to create
            
        Returns:
            DeviceModel: The created device
            
        Raises:
            ValueError: If the device type is invalid
        """
        try:
            # Create the device in the database
            db_device = DeviceModel(
                name=device.name,
                type=device.type,
                hostname=device.hostname,
                action_url=device.action_url,
                friendly_name=device.friendly_name,
                manufacturer=device.manufacturer,
                location=device.location,
                status="connected",  # Set status to connected when creating a new device
                config=device.config,
            )
            self.db.add(db_device)
            self.db.commit()
            self.db.refresh(db_device)
            
            # Register the device with the device manager
            device_info = {
                "device_name": device.name,
                "type": device.type,
                "hostname": device.hostname,
                "action_url": device.action_url,
                "friendly_name": device.friendly_name,
                "manufacturer": device.manufacturer,
                "location": device.location,
            }
            if device.config:
                device_info.update(device.config)
            
            self.device_manager.register_device(device_info)
            
            # Initialize device status
            self.device_manager.update_device_status(
                device_name=device.name,
                status="connected",
                is_playing=False
            )
            
            return db_device
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error creating device: {e}")
            raise
    
    def update_device(self, device_id: int, device: DeviceUpdate) -> Optional[Dict[str, Any]]:
        """
        Update a device
        
        Args:
            device_id: ID of the device to update
            device: Device data to update
            
        Returns:
            Optional[Dict[str, Any]]: The updated device as a dictionary if found, None otherwise
        """
        try:
            # Get the device model
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                return None

            original_device_name_before_update = db_device.name # Capture name before any modifications
            
            # Update the device in the database
            # Explicitly update fields from the Pydantic model to avoid potential issues with model_dump()
            # if the 'device' object is not a fully standard Pydantic instance in this context.
            
            if "name" in device.model_fields_set:
                db_device.name = device.name
            if "type" in device.model_fields_set:
                db_device.type = device.type
            if "hostname" in device.model_fields_set:
                db_device.hostname = device.hostname
            if "friendly_name" in device.model_fields_set:
                db_device.friendly_name = device.friendly_name
            if "action_url" in device.model_fields_set:
                db_device.action_url = device.action_url
            if "manufacturer" in device.model_fields_set:
                db_device.manufacturer = device.manufacturer
            if "location" in device.model_fields_set:
                db_device.location = device.location
            if "status" in device.model_fields_set:
                logger.debug(f"Pydantic device.status is: {device.status}")
                db_device.status = device.status
                logger.debug(f"db_device.status AFTER assignment is: {db_device.status}")
            if "is_playing" in device.model_fields_set:
                db_device.is_playing = device.is_playing
            if "current_video" in device.model_fields_set:
                db_device.current_video = device.current_video
            if "playback_position" in device.model_fields_set:
                db_device.playback_position = device.playback_position
            if "playback_duration" in device.model_fields_set:
                db_device.playback_duration = device.playback_duration
            if "playback_progress" in device.model_fields_set:
                db_device.playback_progress = device.playback_progress
            if "config" in device.model_fields_set:
                db_device.config = device.config
            
            logger.debug(f"db_device.status before commit: {db_device.status}")
            self.db.add(db_device) # Explicitly add to session before commit
            self.db.commit()
            
            # Re-fetch the device to ensure we have the latest data from the DB
            current_db_device_state = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            
            if not current_db_device_state:
                logger.error(f"Device {device_id} not found after commit and explicit re-fetch.")
                return None
            
            logger.debug(f"current_db_device_state.status after re-fetch: {current_db_device_state.status}")
            # The manual override current_db_device_state.status = "offline" is now removed to observe true behavior.
            
            # Update the device in the device manager
            device_info = {
                "device_name": current_db_device_state.name,
                "type": current_db_device_state.type,
                "hostname": current_db_device_state.hostname,
                "action_url": current_db_device_state.action_url,
                "friendly_name": current_db_device_state.friendly_name,
                "manufacturer": current_db_device_state.manufacturer,
                "location": current_db_device_state.location,
                "status": current_db_device_state.status,
            }
            if current_db_device_state.config:
                device_info["config"] = current_db_device_state.config 
            
            # Register device with new info (handles updates atomically)
            self.device_manager.register_device(device_info)
            
            # Update device status in device manager to match database
            self.device_manager.update_device_status(
                device_name=current_db_device_state.name,
                status=current_db_device_state.status,
                is_playing=current_db_device_state.is_playing,
                current_video=current_db_device_state.current_video
            )
            
            # Clean up old name AFTER registering new one to avoid race condition
            if current_db_device_state.name != original_device_name_before_update:
                logger.info(f"Device name changed from {original_device_name_before_update} to {current_db_device_state.name}, cleaning up old entry")
                self.device_manager.unregister_device(original_device_name_before_update)
            
            return self._device_to_dict(current_db_device_state) # Pass the (now manually corrected) fresh DB state
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error updating device: {e}")
            raise
    
    def delete_device(self, device_id: int) -> bool:
        """
        Delete a device
        
        Args:
            device_id: ID of the device to delete
            
        Returns:
            bool: True if the device was deleted, False otherwise
        """
        try:
            # Get the device model
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                return False
            
            # Get the device name for unregistering
            device_name = db_device.name
            
            # Delete the device from the database
            self.db.delete(db_device)
            self.db.commit()
            
            # Unregister the device from the device manager
            self.device_manager.unregister_device(device_name)
            
            return True
        except SQLAlchemyError as e:
            self.db.rollback()
            logger.error(f"Error deleting device: {e}")
            raise
    
    def set_user_control(self, device_id: int, mode: str, reason: str = None, expires_in_seconds: int = None) -> bool:
        """
        Set user control mode for a device
        
        Args:
            device_id: ID of the device
            mode: Control mode ('auto', 'manual', 'overlay', 'renderer')
            reason: Optional reason for the mode change
            expires_in_seconds: Optional expiration time in seconds
            
        Returns:
            bool: True if successful
        """
        try:
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found")
                return False
            
            db_device.user_control_mode = mode
            db_device.user_control_reason = reason
            
            if expires_in_seconds:
                from datetime import datetime, timedelta, timezone
                db_device.user_control_expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in_seconds)
            else:
                db_device.user_control_expires_at = None
            
            self.db.commit()
            logger.info(f"Set device {db_device.name} to {mode} mode, reason: {reason}")
            return True
            
        except Exception as e:
            logger.error(f"Error setting user control mode: {e}")
            self.db.rollback()
            return False
    
    def play_video(self, device_id: int, video_path: str, loop: bool = False) -> bool:
        """
        Play a video on a device
        
        Args:
            device_id: ID of the device to play the video on
            video_path: Path to the video file
            loop: Whether to loop the video
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            device = self.get_device_instance(device_id)
            if not device:
                logger.error(f"Device with ID {device_id} not found")
                return False
            if not os.path.isabs(video_path):
                video_path = os.path.abspath(video_path)
            if not os.path.exists(video_path):
                logger.error(f"Video file {video_path} does not exist")
                return False
            # Check if this device already has a stream for this video
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            video_url = None
            
            if db_device and db_device.streaming_url and db_device.current_video == video_path:
                # Validate the stream is still alive
                import requests
                try:
                    # Quick HEAD request to check if server is responding
                    response = requests.head(db_device.streaming_url, timeout=1)
                    if response.status_code < 400:
                        # Reuse existing stream
                        logger.info(f"Reusing existing stream for {video_path} on port {db_device.streaming_port}")
                        video_url = db_device.streaming_url
                        
                        # Ensure session is registered in StreamingSessionRegistry
                        from core.streaming_registry import StreamingSessionRegistry
                        registry = StreamingSessionRegistry.get_instance()
                        # Check if session already exists
                        existing_sessions = registry.get_sessions_for_device(device.name)
                        session_exists = any(s.server_port == db_device.streaming_port for s in existing_sessions)
                        
                        if not session_exists:
                            session = registry.register_session(
                                device_name=device.name,
                                video_path=video_path,
                                server_ip=db_device.streaming_url.split(':')[1].strip('//'),
                                server_port=db_device.streaming_port
                            )
                            logger.info(f"Re-registered streaming session {session.session_id} for existing stream")
                    else:
                        logger.warning(f"Existing stream at {db_device.streaming_url} returned {response.status_code}, creating new stream")
                        raise Exception("Stream not accessible")
                except Exception as e:
                    logger.warning(f"Existing stream at {db_device.streaming_url} is not accessible: {e}")
                    # Clear stale stream info and create new one
                    db_device.streaming_url = None
                    db_device.streaming_port = None
                    self.db.commit()
                    # Fall through to create new stream
                    video_url = None
            
            if not video_url:
                # Start new streaming server
                from core.twisted_streaming import TwistedStreamingServer
                streaming_server = TwistedStreamingServer.get_instance()
                file_name = os.path.basename(video_path)
                files_dict = {file_name: video_path}
                serve_ip = self.device_manager.get_serve_ip() if hasattr(self.device_manager, 'get_serve_ip') else '127.0.0.1'
                
                try:
                    urls, server = streaming_server.start_server(files=files_dict, serve_ip=serve_ip, port=9000)
                    video_url = urls[file_name]
                    # Extract port from URL
                    import re
                    port_match = re.search(r':(\d+)/', video_url)
                    streaming_port = int(port_match.group(1)) if port_match else None
                    
                    # Update database with streaming info
                    if db_device:
                        db_device.streaming_url = video_url
                        db_device.streaming_port = streaming_port
                        db_device.current_video = video_path
                        self.db.commit()
                        
                        # Register session with StreamingSessionRegistry so monitoring thread can track it
                        from core.streaming_registry import StreamingSessionRegistry
                        registry = StreamingSessionRegistry.get_instance()
                        
                        # Clean up any existing sessions for this device before creating new one
                        existing_sessions = registry.get_sessions_for_device(device.name)
                        for existing_session in existing_sessions:
                            logger.info(f"Cleaning up existing session {existing_session.session_id} before playing new video")
                            registry.unregister_session(existing_session.session_id)
                        
                        session = registry.register_session(
                            device_name=device.name,
                            video_path=video_path,
                            server_ip=serve_ip,
                            server_port=streaming_port
                        )
                        logger.info(f"Registered streaming session {session.session_id} for device {device.name}")
                except RuntimeError as e:
                    if "No available port" in str(e):
                        logger.error(f"Port exhaustion: {e}")
                        # Try to clean up and retry once
                        streaming_server.cleanup_old_servers(keep_last=3)
                        urls, server = streaming_server.start_server(files=files_dict, serve_ip=serve_ip, port=9000)
                        video_url = urls[file_name]
                    else:
                        raise
            
            if video_url:
                logger.info(f"Playing video {video_url} on device {device_id} (loop={loop})")
                # Set the video file path on the device for duration detection
                if hasattr(device, 'current_video_path'):
                    device.current_video_path = video_path
                success = device.play(video_url, loop)
            else:
                logger.error(f"No video URL available for device {device_id}")
                return False
            if success:
                # First ensure device is marked as not playing to trigger timestamp update
                db_device.is_playing = False
                self.db.commit()
                
                # Get video duration using ffprobe
                try:
                    import subprocess
                    result = subprocess.run(
                        ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
                         '-of', 'default=noprint_wrappers=1:nokey=1', video_path],
                        capture_output=True, text=True, timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        duration_seconds = int(float(result.stdout.strip()))
                        hours = duration_seconds // 3600
                        minutes = (duration_seconds % 3600) // 60
                        seconds = duration_seconds % 60
                        duration_str = f"{hours:02d}:{minutes:02d}:{seconds:02d}"
                        
                        # Update the device with video info
                        db_device.current_video = video_path
                        db_device.playback_duration = duration_str
                        self.db.commit()
                        logger.info(f"Set video duration: {duration_str}")
                except Exception as e:
                    logger.warning(f"Could not get video duration: {e}")
                
                # Set user control mode to manual since user initiated this
                db_device.user_control_mode = "manual"
                db_device.user_control_reason = "user_play"
                self.db.commit()
                
                # Now update to playing - this will set the timestamp
                self.update_device_status(device.name, "connected", is_playing=True)
                logger.info(f"Video {video_url} is now playing on device {device_id}")
                return True
            else:
                logger.error(f"Failed to play video {video_url} on device {device_id}")
                return False
        except Exception as e:
            logger.error(f"Error playing video on device {device_id}: {e}")
            logger.error(traceback.format_exc())
            return False
    
    def stop_video(self, device_id: int) -> bool:
        """
        Stop playback on a device
        
        Args:
            device_id: ID of the device to stop playback on
            
        Returns:
            bool: True if playback was stopped, False otherwise
        """
        try:
            # Get the device model
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False
            
            # Get the device from the device manager
            core_device = self.device_manager.get_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                return False
            
            # Stop playback
            logger.info(f"Stopping playback on device {db_device.name}")
            success = core_device.stop()
            
            # Clear streaming info from database and set user control
            if success:
                db_device.streaming_url = None
                db_device.streaming_port = None
                db_device.current_video = None
                db_device.user_control_mode = "manual"
                db_device.user_control_reason = "user_stopped"
                self.db.commit()
                
                # Stop streaming server
                streaming_service = getattr(self.device_manager, 'streaming_service', None)
                if streaming_service:
                    logger.info(f"Stopping streaming servers for device {db_device.name}")
                    streaming_service.stop_all_servers()
                
                # Unregister streaming session
                streaming_registry = getattr(self.device_manager, 'streaming_registry', None)
                if streaming_registry:
                    sessions = streaming_registry.get_sessions_for_device(db_device.name)
                    for session_id in sessions:
                        logger.info(f"Unregistering streaming session {session_id} for device {db_device.name}")
                        streaming_registry.unregister_session(session_id)
                
                # Clean up all device state in device manager
                logger.info(f"Cleaning up device state for {db_device.name}")
                self.device_manager.cleanup_device_state(db_device.name)
            
            # Update the device status in the database
            if success:
                self.update_device_status(db_device.name, "connected", is_playing=False)
                logger.info(f"Successfully stopped playback on device {db_device.name}")
            else:
                logger.error(f"Failed to stop playback on device {db_device.name}")
            
            return success
        except Exception as e:
            logger.error(f"Error stopping playback on device {device_id}: {e}")
            return False
    
    def pause_video(self, device_id: int) -> bool:
        """
        Pause playback on a device
        
        Args:
            device_id: ID of the device to pause playback on
            
        Returns:
            bool: True if playback was paused, False otherwise
        """
        try:
            # Get the device model
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False
            
            # Get the device from the device manager
            core_device = self.device_manager.get_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                return False
            
            # Pause playback
            logger.info(f"Pausing playback on device {db_device.name}")
            success = core_device.pause()
            
            # Update the device status in the database
            if success:
                self.update_device_status(db_device.name, "connected", is_playing=False)
                logger.info(f"Successfully paused playback on device {db_device.name}")
            else:
                logger.error(f"Failed to pause playback on device {db_device.name}")
            
            return success
        except Exception as e:
            logger.error(f"Error pausing playback on device {device_id}: {e}")
            return False
    
    def seek_video(self, device_id: int, position: str) -> bool:
        """
        Seek to a position in the current video
        
        Args:
            device_id: ID of the device to seek on
            position: Position to seek to (format: HH:MM:SS)
            
        Returns:
            bool: True if the seek was successful, False otherwise
        """
        try:
            # Get the device model
            db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
            if not db_device:
                logger.error(f"Device with ID {device_id} not found in database")
                return False
            
            # Get the device from the device manager
            core_device = self.device_manager.get_device(db_device.name)
            if not core_device:
                logger.error(f"Device {db_device.name} not found in device manager")
                
                # Try to register the device if it's not in the device manager
                device_info = {
                    "device_name": db_device.name,
                    "type": db_device.type,
                    "hostname": db_device.hostname,
                    "action_url": db_device.action_url,
                    "friendly_name": db_device.friendly_name,
                    "manufacturer": db_device.manufacturer,
                    "location": db_device.location,
                }
                
                # Add any additional config from the database
                if db_device.config:
                    device_info.update(db_device.config)
                
                # Register the device
                core_device = self.device_manager.register_device(device_info)
                if not core_device:
                    logger.error(f"Failed to register device {db_device.name}")
                    return False
                
                logger.info(f"Registered device {db_device.name} from database")
            
            # Seek to the position
            logger.info(f"Seeking to position {position} on device {db_device.name}")
            success = core_device.seek(position)
            
            if success:
                logger.info(f"Successfully seeked to position {position} on device {db_device.name}")
            else:
                logger.error(f"Failed to seek to position {position} on device {db_device.name}")
            
            return success
        except Exception as e:
            logger.error(f"Error seeking on device {device_id}: {e}")
            return False
    
    def discover_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Discover DLNA devices on the network
        
        Args:
            timeout: Timeout for discovery in seconds
            
        Returns:
            List[Dict[str, Any]]: List of discovered devices as dictionaries
        """
        try:
            logger.debug(f"Starting device discovery with timeout {timeout} seconds")
            # Use the device manager to discover devices directly
            discovered_devices = self.device_manager._discover_dlna_devices(timeout=timeout)
            logger.debug(f"Discovered devices: {discovered_devices}")
            
            # First, check which devices already exist in the database and core manager
            existing_devices = {}
            for db_device in self.db.query(DeviceModel).all():
                existing_devices[db_device.name] = {
                    "db_device": db_device,
                    "core_device": self.device_manager.get_device(db_device.name)
                }
            
            # First, check the streaming registry to see what devices are actively streaming
            from core.streaming_registry import StreamingSessionRegistry
            streaming_registry = StreamingSessionRegistry.get_instance()
            active_streaming_devices = set()
            try:
                # Get all active streaming sessions
                active_sessions = streaming_registry.get_active_sessions()
                for session in active_sessions:
                    active_streaming_devices.add(session.device_name)
                    logger.info(f"Device {session.device_name} has active streaming sessions, skipping auto-play")
            except Exception as e:
                logger.error(f"Error checking streaming registry: {e}")
                logger.exception("Detailed streaming registry error:")
            
            # Save discovered devices to database
            db_devices = []
            discovered_names = set()
            
            for device_info in discovered_devices:
                device_name = device_info.get("friendly_name") or device_info.get("name") or device_info.get("device_name")
                logger.info(f"Processing discovered device: {device_name}")
                discovered_names.add(device_name)
                
                # Ensure all required fields are present
                device_info["device_name"] = device_name
                # Always set DB name to canonical device_name
                if "name" in device_info:
                    device_info["name"] = device_name
                else:
                    device_info.update({"name": device_name})
                device_info["type"] = "dlna"
                
                # Check if device exists in database and core manager
                existing_data = existing_devices.get(device_name)
                
                if existing_data:
                    db_device = existing_data["db_device"]
                    core_device = existing_data["core_device"]
                    
                    logger.info(f"Device {device_name} already exists in database, updating status only")
                    
                    # Only update the connection status to connected - don't modify any other fields
                    db_device.status = "connected"
                    self.db.commit()
                    self.db.refresh(db_device)
                    
                    # Check multiple sources to determine if the device is playing
                    is_already_playing = False
                    
                    # Check 1: Device is in active streaming sessions
                    if device_name in active_streaming_devices:
                        is_already_playing = True
                        logger.info(f"Device {device_name} has active streaming sessions")
                    
                    # Check 2: Core device reports it's playing
                    if core_device and core_device.is_playing:
                        is_already_playing = True
                        logger.info(f"Device {device_name} reports is_playing=True")
                    
                    # Check 3: DB says it's playing
                    if db_device.is_playing:
                        is_already_playing = True
                        logger.info(f"Database shows device {device_name} is_playing=True")
                    
                    # Check 4: Device has a current video assigned
                    if db_device.current_video:
                        is_already_playing = True
                        logger.info(f"Device {device_name} has current_video={db_device.current_video}")
                    
                    # Update the database if playing state is detected
                    if is_already_playing:
                        db_device.is_playing = True
                        self.db.commit()
                        logger.info(f"Updated device {device_name} playing status")
                    
                    # Add to the result list
                    db_devices.append(db_device)
                else:
                    # This is a new device not yet in the database
                    logger.info(f"Creating new device {device_name} in database")
                    # Create the device in the database
                    db_device = DeviceModel(
                        name=device_name,
                        type=device_info.get("type", "dlna"),
                        hostname=device_info.get("hostname", ""),
                        action_url=device_info.get("action_url", ""),
                        friendly_name=device_info.get("friendly_name", device_name),
                        manufacturer=device_info.get("manufacturer", ""),
                        location=device_info.get("location", ""),
                        status="connected",  # Set status to connected when discovered
                        is_playing=False,
                        config=device_info,
                    )
                    self.db.add(db_device)
                    self.db.commit()
                    self.db.refresh(db_device)
                    
                    # Register the device with the device manager
                    core_device = self.device_manager.register_device(device_info)
                    
                    # Try auto-play for new devices only
                    config_service = ConfigService.get_instance()
                    device_config = config_service.get_device_config(device_name)
                    
                    if device_config and "video_file" in device_config:
                        video_path = device_config["video_file"]
                        if os.path.exists(video_path):
                            logger.info(f"Auto-playing video {video_path} on new device {device_name}")
                            if core_device:
                                success = self.device_manager.auto_play_video(core_device, video_path, loop=True)
                                if success:
                                    # Update the device status in the database
                                    db_device.status = "connected"
                                    db_device.is_playing = True
                                    db_device.current_video = video_path
                                    self.db.commit()
                                    logger.info(f"Updated device {device_name} status in database")
                        else:
                            logger.error(f"Video file not found: {video_path}")
                    
                    # Add to the list of devices
                    db_devices.append(db_device)
            
            # Update the status of all devices (both found and not found)
            logger.info(f"Discovered names for sync: {discovered_names}")
            self.sync_device_status_with_discovery(discovered_names)
            
            # Always include a 'name' key in the returned dicts for sync logic
            result = []
            for device in db_devices:
                d = device.to_dict()
                if 'name' not in d and 'friendly_name' in d:
                    d['name'] = d['friendly_name']
                result.append(d)
            return result
        except Exception as e:
            logger.error(f"Error discovering devices: {e}")
            traceback.print_exc()
            return []
    
    def load_devices_from_config(self, config_file: str) -> List[Dict[str, Any]]:
        """
        Load devices from a configuration file
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            List[Dict[str, Any]]: List of loaded devices as dictionaries
        """
        try:
            # Log the absolute path for debugging
            abs_path = os.path.abspath(config_file)
            logger.info(f"Loading devices from config file: {abs_path}")
            
            # Load the configuration file directly
            with open(abs_path, "r") as f:
                config_data = json.load(f)
            
            # Handle different config file formats
            if "devices" in config_data:
                # Format: {"devices": [{device1}, {device2}, ...]}
                devices_config = config_data["devices"]
            else:
                # Format: [{device1}, {device2}, ...]
                devices_config = config_data
            
            logger.info(f"Found {len(devices_config)} devices in config file")
            
            config_dir = os.path.dirname(abs_path)

            # Register devices with the device manager and create them in the database
            db_devices = []
            for device_info in devices_config:
                device_info = dict(device_info)
                device_name = device_info.get("device_name") or device_info.get("name") # Check for "name" as well
                if not device_name:
                    logger.error("Device missing 'device_name' or 'name' in config file entry")
                    continue

                video_file = device_info.get("video_file")
                if video_file:
                    resolved_video_file = os.path.expanduser(os.path.expandvars(video_file))
                    if not os.path.isabs(resolved_video_file):
                        resolved_video_file = os.path.abspath(os.path.join(config_dir, resolved_video_file))
                    device_info["video_file"] = resolved_video_file
                
                # Ensure device_info uses "device_name" consistently internally if "name" was used
                if "name" in device_info and "device_name" not in device_info:
                    device_info["device_name"] = device_name
                
                # Check if the device already exists in the database
                db_device = self.get_device_by_name(device_name)
                if db_device:
                    logger.info(f"Device {device_name} already exists in database, updating")
                    # Update the device in the database
                    for key, value in device_info.items():
                        if hasattr(db_device, key):
                            setattr(db_device, key, value)
                    
                    # Don't automatically set status to connected on config load
                    # Let discovery determine actual status
                    db_device.status = "disconnected"
                    
                    # Update the config field, ensuring to only pass the 'config' sub-dictionary
                    db_device.config = device_info.get("config")
                    
                    # Commit the changes
                    self.db.commit()
                    self.db.refresh(db_device)
                    
                    # Add to the list of devices
                    db_devices.append(db_device)
                else:
                    logger.info(f"Creating new device {device_name} in database")
                    # Create the device in the database
                    db_device = DeviceModel(
                        name=device_name,
                        type=device_info.get("type", "dlna"),
                        hostname=device_info.get("hostname", ""),
                        action_url=device_info.get("action_url", ""),
                        friendly_name=device_info.get("friendly_name", device_name),
                        manufacturer=device_info.get("manufacturer", ""),
                        location=device_info.get("location", ""),
                        status="disconnected",  # Start as disconnected, let discovery determine actual status
                        is_playing=False,
                        config=device_info.get("config"), # Only pass the 'config' sub-dictionary
                    )
                    self.db.add(db_device)
                    self.db.commit()
                    self.db.refresh(db_device)
                    
                    # Add to the list of devices
                    db_devices.append(db_device)
                
                # Register the device with the device manager
                self.device_manager.register_device(device_info)
                
                # Update device status in device manager
                self.device_manager.update_device_status(
                    device_name=device_name,
                    status="disconnected"  # Start as disconnected until discovery confirms
                )
            
            # Return the devices as dictionaries
            return [device.to_dict() for device in db_devices]
        except Exception as e:
            self.db.rollback()
            logger.error(f"Error loading devices from config: {e}")
            return []
    
    def update_device_status(self, device_name: str, status: str, is_playing: bool = False) -> bool:
        """
        Update the status of a device in the database
        
        Args:
            device_name: Name of the device to update
            status: New status for the device
            is_playing: Whether the device is currently playing
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get the device from the database
            device = self.db.query(DeviceModel).filter(DeviceModel.name == device_name).first()
            if not device:
                logger.error(f"Device {device_name} not found in database")
                return False
            
            # Update device status
            device.status = status
            
            # Track playback state changes
            was_playing = device.is_playing
            
            if is_playing and not was_playing:
                # Starting playback - store start time
                device.playback_position = "00:00:00"
                device.playback_progress = 0
                # Store start time
                device.playback_started_at = datetime.now(timezone.utc)
                device.updated_at = datetime.now(timezone.utc)
                logger.info(f"Device {device_name} started playing at {device.updated_at}")
            elif not is_playing and was_playing:
                # Stopping playback
                device.current_video = None
                device.playback_position = "00:00:00"
                device.playback_progress = 0
                device.playback_started_at = None
                device.updated_at = datetime.now(timezone.utc)
            
            device.is_playing = is_playing
            
            # Update device manager status
            core_device = self.device_manager.get_device(device_name)
            if core_device:
                core_device.update_status(status)
                core_device.update_playing(is_playing)
                if not is_playing:
                    core_device.update_video(None)
            
            # Commit changes
            self.db.commit()
            logger.info(f"Updated device {device_name} status to {status} (playing: {is_playing})")
            return True
        except Exception as e:
            logger.error(f"Error updating device {device_name} status: {e}")
            return False
    
    def save_devices_to_config(self, config_file: str) -> bool:
        """
        Save devices to a configuration file
        
        Args:
            config_file: Path to the configuration file
            
        Returns:
            bool: True if the devices were saved, False otherwise
        """
        try:
            return self.device_manager.save_devices_to_config(config_file)
        except Exception as e:
            logger.error(f"Error saving devices to config: {e}")
            return False
    
    def _get_playback_started_at(self, device: DeviceModel) -> Optional[str]:
        """
        Get the playback start time for a device.
        If the device is playing but updated_at is old, assume it just started.
        """
        if not device.is_playing:
            return None
            
        if not device.updated_at:
            # No timestamp, assume just started
            return datetime.now(timezone.utc).isoformat()
            
        # If we have a duration, check if updated_at is older than the duration
        if device.playback_duration:
            try:
                # Parse duration to seconds
                parts = device.playback_duration.split(':')
                duration_seconds = int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
                
                # Check how long ago updated_at was
                time_since_update = (datetime.now(timezone.utc) - device.updated_at).total_seconds()
                
                # If updated_at is older than the video duration, assume video just started
                if time_since_update > duration_seconds:
                    return datetime.now(timezone.utc).isoformat()
            except Exception as e:
                logger.warning(f"Error parsing duration for playback time calculation: {e}")
        
        # Otherwise use updated_at
        return device.updated_at.isoformat()

    def _format_datetime_utc(self, dt: Optional[datetime]) -> Optional[str]:
        """
        Format datetime to ISO format with UTC timezone indicator
        
        Args:
            dt: Datetime object (may or may not have timezone info)
            
        Returns:
            ISO formatted string with 'Z' suffix for UTC, or None
        """
        if not dt:
            return None
        
        # If datetime has no timezone info, assume it's UTC
        if dt.tzinfo is None:
            return dt.isoformat() + 'Z'
        
        # If it has timezone info, convert to UTC and format
        utc_dt = dt.astimezone(timezone.utc)
        # Use 'Z' suffix for UTC instead of '+00:00'
        return utc_dt.isoformat().replace('+00:00', 'Z')
    
    def _device_to_dict(self, device: DeviceModel) -> Dict[str, Any]: # Renamed from _device_model_to_dict
        """
        Convert a DeviceModel to a dictionary, incorporating live status from DeviceManager.
        """
        # Start with DB data
        device_dict = {
            "id": device.id,
            "name": device.name,
            "type": device.type,
            "hostname": device.hostname,
            "friendly_name": device.friendly_name,
            "location": device.location,
            "manufacturer": device.manufacturer,
            "action_url": device.action_url,
            "status": device.status, # This is the DB status
            "is_playing": device.is_playing,
            "current_video": device.current_video,
            "playback_position": device.playback_position,
            "playback_duration": device.playback_duration,
            "playback_progress": device.playback_progress,
            "playback_started_at": self._format_datetime_utc(device.playback_started_at),
            "config": device.config,
            "created_at": self._format_datetime_utc(device.created_at),
            "updated_at": self._format_datetime_utc(device.updated_at),
        }

        # Debug logging
        logger.debug(f"Device {device.name}: is_playing={device.is_playing}, updated_at={device.updated_at}, playback_started_at={device_dict.get('playback_started_at')}")
        
        # Override with live status from DeviceManager if available
        logger.debug(f"_device_to_dict for device.name='{device.name}'")
        logger.debug(f"_device_to_dict: self.device_manager.device_status keys: {list(self.device_manager.device_status.keys())}")
        
        with self.device_manager.device_state_lock:
            if device.name in self.device_manager.device_status:
                logger.debug(f"_device_to_dict: Found '{device.name}' in device_manager.device_status")
                status_info = self.device_manager.device_status[device.name]
                # Prioritize live status from manager
                device_dict["status"] = status_info.get("status", device.status) # Fallback to DB status if manager's status is None
                # Add additional live info from device_status
                device_dict["last_seen"] = status_info.get("last_updated")
                device_dict["manager_is_playing"] = status_info.get("is_playing", device.is_playing)
                device_dict["last_seen_at"] = status_info.get("last_seen_at")
                device_dict["last_lost_at"] = status_info.get("last_lost_at")
                device_dict["reconnect_count"] = status_info.get("reconnect_count", 0)
                device_dict["degraded_count"] = status_info.get("degraded_count", 0)
                device_dict["offline_count"] = status_info.get("offline_count", 0)
                logger.debug(
                    "Device %s status from manager: %s, is_playing: %s",
                    device.name,
                    status_info.get("status"),
                    status_info.get("is_playing"),
                )
            else:
                logger.debug(
                    "Device '%s' not found in device_manager.device_status, using DB status: %s",
                    device.name,
                    device.status,
                )

        device_dict.update(self._derive_device_runtime_state(device, device_dict))
        logger.debug(f"_device_to_dict: final device_dict['status'] for '{device.name}' is '{device_dict['status']}'")
        return device_dict

    def _derive_device_runtime_state(self, device: DeviceModel, device_dict: Dict[str, Any]) -> Dict[str, Any]:
        """
        Produce stable, presentation-friendly availability fields from raw DB and manager state.
        This does not change persisted device status; it only normalizes what the frontend sees.
        """
        now = time.time()
        timeout = getattr(self.device_manager, "connectivity_timeout", 30)
        degraded_threshold = timeout
        offline_threshold = timeout * 2

        manager_status = device_dict.get("status") or device.status or "unknown"
        manager_is_playing = device_dict.get("manager_is_playing", device_dict.get("is_playing", False))
        last_seen_raw = device_dict.get("last_seen")

        last_seen_ts = None
        if isinstance(last_seen_raw, (int, float)):
            last_seen_ts = float(last_seen_raw)

        seconds_since_seen = None if last_seen_ts is None else max(0.0, now - last_seen_ts)

        if manager_status in {"playing", "connected"}:
            if seconds_since_seen is None or seconds_since_seen <= degraded_threshold:
                availability = "online"
            elif seconds_since_seen <= offline_threshold:
                availability = "degraded"
            else:
                availability = "offline"
        elif manager_status in {"streaming_issue", "error"}:
            availability = "degraded" if seconds_since_seen is None or seconds_since_seen <= offline_threshold else "offline"
        elif manager_status in {"disconnected", "offline"}:
            availability = "offline"
        else:
            availability = "unknown"

        connected_since = None
        downtime_started_at = None
        uptime_seconds = None
        downtime_seconds = None
        last_lost_at = device_dict.get("last_lost_at")

        if availability in {"online", "degraded"} and last_seen_ts is not None:
            connected_since = last_seen_ts if seconds_since_seen is None else max(last_seen_ts - min(seconds_since_seen, degraded_threshold), 0)
            uptime_seconds = max(0.0, now - connected_since)
        elif availability == "offline":
            if isinstance(last_lost_at, (int, float)):
                downtime_started_at = float(last_lost_at)
                downtime_seconds = max(0.0, now - downtime_started_at)
            elif last_seen_ts is not None:
                downtime_started_at = last_seen_ts + offline_threshold
                downtime_seconds = max(0.0, now - downtime_started_at)

        overlay_cast = self._get_overlay_cast_state(device)

        return {
            "availability": availability,
            "derived_status": availability,
            "manager_status": manager_status,
            "manager_is_playing": manager_is_playing,
            "seconds_since_seen": seconds_since_seen,
            "connected_since": connected_since,
            "uptime_seconds": uptime_seconds,
            "downtime_started_at": downtime_started_at,
            "downtime_seconds": downtime_seconds,
            "last_seen_at": device_dict.get("last_seen_at"),
            "last_lost_at": last_lost_at,
            "reconnect_count": int(device_dict.get("reconnect_count", 0) or 0),
            "degraded_count": int(device_dict.get("degraded_count", 0) or 0),
            "offline_count": int(device_dict.get("offline_count", 0) or 0),
            **overlay_cast,
        }

    def _get_overlay_cast_state(self, device: DeviceModel) -> Dict[str, Any]:
        active_session = None
        cast_service = get_overlay_cast_service()
        for session in cast_service.list_sessions():
            if session.get("archived"):
                continue
            if self._overlay_session_matches_device(session, device):
                active_session = session
                break

        if not active_session:
            return {
                "active_overlay_cast": False,
                "overlay_cast_status": None,
                "overlay_cast_started_at": None,
                "overlay_cast_uptime_seconds": None,
                "overlay_cast_current_step": None,
                "overlay_cast_ffmpeg_speed": None,
                "overlay_cast_ffmpeg_fps": None,
                "overlay_cast_ffmpeg_bitrate_kbps": None,
                "overlay_cast_active_clients": 0,
                "overlay_cast_session_id": None,
            }

        started_at_raw = active_session.get("started_at")
        started_at = None
        overlay_cast_uptime_seconds = None
        if started_at_raw:
            if isinstance(started_at_raw, str):
                try:
                    started_at = datetime.fromisoformat(started_at_raw)
                except ValueError:
                    started_at = None
            elif isinstance(started_at_raw, datetime):
                started_at = started_at_raw
            if started_at is not None:
                overlay_cast_uptime_seconds = max(
                    0.0,
                    (datetime.utcnow() - started_at.replace(tzinfo=None)).total_seconds(),
                )

        return {
            "active_overlay_cast": True,
            "overlay_cast_status": active_session.get("status"),
            "overlay_cast_started_at": started_at_raw,
            "overlay_cast_uptime_seconds": overlay_cast_uptime_seconds,
            "overlay_cast_current_step": active_session.get("current_step"),
            "overlay_cast_ffmpeg_speed": active_session.get("ffmpeg_speed"),
            "overlay_cast_ffmpeg_fps": active_session.get("ffmpeg_fps"),
            "overlay_cast_ffmpeg_bitrate_kbps": active_session.get("ffmpeg_bitrate_kbps"),
            "overlay_cast_active_clients": active_session.get("active_clients", 0),
            "overlay_cast_session_id": active_session.get("session_id"),
        }

    def _overlay_session_matches_device(self, session: Dict[str, Any], device: DeviceModel) -> bool:
        device_id = session.get("device_id")
        if not device_id or device.type != "dlna" or not device.hostname:
            return False

        expected_prefix = f"dlna_{device.hostname}_"
        if device_id.startswith(expected_prefix):
            return True

        if device.action_url:
            parsed = urlparse(device.action_url)
            if parsed.hostname == device.hostname and parsed.port is not None:
                return device_id == f"dlna_{parsed.hostname}_{parsed.port}"

        return False

    def sync_device_status_with_discovery(self, discovered_device_names: set) -> None:
        """
        Sync the status of all devices in the database and in-memory with the current discovery results.
        Devices not found in the latest discovery are marked as 'disconnected'.
        Devices found are marked as 'connected' while preserving their playing status.
        """
        all_devices = self.db.query(DeviceModel).all()
        for device in all_devices:
            if device.name not in discovered_device_names:
                self.update_device_status(device.name, "disconnected", is_playing=False)
            else:
                # Preserve the device's playing status when it's found in discovery
                core_device = self.device_manager.get_device(device.name)
                is_playing = False
                
                # Check if the device is playing from multiple sources
                if core_device and core_device.is_playing:
                    is_playing = True
                elif device.is_playing:
                    is_playing = True
                elif device.current_video:
                    is_playing = True
                    
                self.update_device_status(device.name, "connected", is_playing=is_playing)

    def get_device_instance(self, device_id: int):
        db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not db_device:
            logger.error(f"[get_device_instance] Device with ID {device_id} not found in DB")
            return None
        logger.debug(f"[get_device_instance] Looking for device '{db_device.name}' in DeviceManager")
        core_device = self.device_manager.get_device(db_device.name)
        if not core_device:
            logger.debug(f"[get_device_instance] Device '{db_device.name}' not found, registering from DB")
            device_info = {
                "device_name": db_device.name,
                "type": db_device.type,
                "hostname": db_device.hostname,
                "action_url": db_device.action_url,
                "friendly_name": db_device.friendly_name,
                "manufacturer": db_device.manufacturer,
                "location": db_device.location,
            }
            if db_device.config:
                device_info.update(db_device.config)
            core_device = self.device_manager.register_device(device_info)
            if not core_device:
                logger.error(f"[get_device_instance] Registration failed for device '{db_device.name}' with info: {device_info}")
        else:
            logger.debug(f"[get_device_instance] Found device '{db_device.name}' in DeviceManager")
        return core_device
