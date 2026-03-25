import logging
import os
import json
import traceback
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
from datetime import datetime

from models.device import DeviceModel
from schemas.device import DeviceCreate, DeviceUpdate
from core.config_service import ConfigService
from services.device_playback_service import DevicePlaybackService
from services.device_discovery_service import DeviceDiscoveryService
from services.device_runtime_sync_service import DeviceRuntimeSyncService
from services.device_view_service import DeviceViewService
from services.app_runtime import get_app_runtime

logger = logging.getLogger(__name__)

class DeviceService:
    """
    Service for managing devices
    """
    def __init__(self, db: Session, device_manager: Optional[object] = None, runtime=None):
        self.db = db
        if runtime is not None:
            self.runtime = runtime
        elif device_manager is not None and hasattr(device_manager, "build_device_service"):
            self.runtime = device_manager
        else:
            self.runtime = get_app_runtime()
        self.runtime_sync_service = DeviceRuntimeSyncService(self.runtime)
        self.device_view_service = DeviceViewService(self.runtime)
        self.device_playback_service = DevicePlaybackService(
            db=db,
            runtime=self.runtime,
            runtime_sync_service=self.runtime_sync_service,
            get_device_instance=self.get_device_instance,
            update_device_status=self.update_device_status,
        )
        self.device_discovery_service = DeviceDiscoveryService(
            db=db,
            runtime=self.runtime,
            runtime_sync_service=self.runtime_sync_service,
            get_device_by_name=self.get_device_by_name,
            update_device_status=self.update_device_status,
        )
    
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

        return self.device_view_service.build_device_detail_dict(device)
    
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
            
            self.runtime_sync_service.register_and_update(
                db_device,
                status="connected",
                is_playing=False,
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
            
            self.runtime_sync_service.register_and_update(
                current_db_device_state,
                status=current_db_device_state.status,
                is_playing=current_db_device_state.is_playing,
                current_video=current_db_device_state.current_video,
            )
            
            # Clean up old name AFTER registering new one to avoid race condition
            if current_db_device_state.name != original_device_name_before_update:
                logger.info(f"Device name changed from {original_device_name_before_update} to {current_db_device_state.name}, cleaning up old entry")
                self.runtime_sync_service.unregister(original_device_name_before_update)
            
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
            self.runtime_sync_service.unregister(device_name)
            
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
        return self.device_playback_service.play_video(device_id, video_path, loop)
    
    def stop_video(self, device_id: int) -> bool:
        return self.device_playback_service.stop_video(device_id)
    
    def pause_video(self, device_id: int) -> bool:
        return self.device_playback_service.pause_video(device_id)
    
    def seek_video(self, device_id: int, position: str) -> bool:
        return self.device_playback_service.seek_video(device_id, position)

    def update_playback_progress(
        self,
        device_id: int,
        position: str,
        duration: str,
        progress: int,
    ) -> bool:
        return self.device_playback_service.update_playback_progress(
            device_id,
            position,
            duration,
            progress,
        )
    
    def discover_devices(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        return self.device_discovery_service.discover_devices(timeout=timeout)
    
    def load_devices_from_config(self, config_file: str) -> List[Dict[str, Any]]:
        return self.device_discovery_service.load_devices_from_config(config_file)
    
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
            core_device = self.runtime_sync_service.get_core_device(device_name)
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
        return self.device_discovery_service.save_devices_to_config(config_file)
    
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

    def _device_to_dict(self, device: DeviceModel) -> Dict[str, Any]: # Renamed from _device_model_to_dict
        return self.device_view_service.build_device_dict(device)

    def _derive_device_runtime_state(self, device: DeviceModel, device_dict: Dict[str, Any]) -> Dict[str, Any]:
        return self.device_view_service.derive_runtime_state(device, device_dict)

    def _get_overlay_cast_state(self, device: DeviceModel) -> Dict[str, Any]:
        return self.device_view_service.get_overlay_cast_state(device)

    def _overlay_session_matches_device(self, session: Dict[str, Any], device: DeviceModel) -> bool:
        return self.device_view_service.overlay_session_matches_device(session, device)

    def sync_device_status_with_discovery(self, discovered_device_names: set) -> None:
        self.device_discovery_service.sync_device_status_with_discovery(discovered_device_names)

    def get_device_instance(self, device_id: int):
        db_device = self.db.query(DeviceModel).filter(DeviceModel.id == device_id).first()
        if not db_device:
            logger.error(f"[get_device_instance] Device with ID {device_id} not found in DB")
            return None
        logger.debug(f"[get_device_instance] Looking for device '{db_device.name}' in runtime inventory")
        core_device = self.runtime_sync_service.get_core_device(db_device.name)
        if not core_device:
            logger.debug(f"[get_device_instance] Device '{db_device.name}' not found, registering from DB")
            device_info = self.runtime_sync_service.build_device_info(db_device)
            core_device = self.runtime_sync_service.register(device_info)
            if not core_device:
                logger.error(f"[get_device_instance] Registration failed for device '{db_device.name}' with info: {device_info}")
        else:
            logger.debug(f"[get_device_instance] Found device '{db_device.name}' in runtime inventory")
        return core_device
