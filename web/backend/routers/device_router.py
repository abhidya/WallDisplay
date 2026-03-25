from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging

from database.database import get_db
from models.device import DeviceModel
from schemas.device import (
    DeviceCreate,
    DeviceUpdate,
    DeviceResponse,
    DeviceList,
    DevicePlayRequest,
    DeviceActionResponse,
)
from services.device_service import DeviceService
from services.app_runtime import get_app_runtime
from routers.video_router import get_video_service

# Set up logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/devices",
    tags=["devices"],
    responses={404: {"description": "Not found"}},
)

# Dependency to get the device service
def get_device_service(db: Session = Depends(get_db)) -> DeviceService:
    return get_app_runtime().build_device_service(db)

@router.get("/discover", response_model=DeviceList)
@router.post("/discover", response_model=DeviceList)
def discover_devices(
    timeout: float = Query(5.0, description="Timeout for discovery in seconds"),
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Discover DLNA devices on the network and update device statuses
    """
    discovered_devices = device_service.discover_devices(timeout=timeout)
    # Return the up-to-date device list
    devices = device_service.get_devices()
    return {
        "devices": devices,
        "total": len(devices),
    }

# Discovery control endpoints - MUST be before /{device_id} routes
@router.post("/discovery/pause", response_model=DeviceActionResponse)
def pause_discovery():
    """Pause the discovery loop"""
    get_app_runtime().pause_discovery()
    return {
        "success": True,
        "message": "Discovery loop paused",
    }

@router.post("/discovery/resume", response_model=DeviceActionResponse)
def resume_discovery():
    """Resume the discovery loop"""
    get_app_runtime().resume_discovery()
    return {
        "success": True,
        "message": "Discovery loop resumed",
    }

@router.get("/discovery/status")
def get_discovery_status():
    """Get discovery loop status"""
    return get_app_runtime().get_discovery_status()

@router.get("/", response_model=DeviceList)
def get_devices(
    skip: int = 0,
    limit: int = 100,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Get all devices
    """
    devices = device_service.get_devices(skip=skip, limit=limit)
    return {
        "devices": devices,
        "total": len(devices),
    }

@router.get("/{device_id}", response_model=DeviceResponse)
def get_device(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Get a device by ID
    """
    device = device_service.get_device_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return device

@router.post("/", response_model=DeviceResponse, status_code=status.HTTP_201_CREATED)
def create_device(
    device: DeviceCreate,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Create a new device
    """
    try:
        return device_service.create_device(device)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

@router.put("/{device_id}", response_model=DeviceResponse)
def update_device(
    device_id: int,
    device: DeviceUpdate,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Update a device
    """
    db_device = device_service.update_device(device_id, device)
    if not db_device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return db_device

@router.delete("/{device_id}", response_model=DeviceActionResponse)
def delete_device(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Delete a device
    """
    success = device_service.delete_device(device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    return {
        "success": True,
        "message": f"Device with ID {device_id} deleted",
    }

@router.post("/{device_id}/play", response_model=DeviceActionResponse)
def play_video(
    device_id: int,
    play_request: DevicePlayRequest,
    sync_overlays: bool = Query(False, description="Sync overlay windows"),
    device_service: DeviceService = Depends(get_device_service),
    video_service = Depends(get_video_service),
):
    """
    Play a video on a device
    """
    logger.info(f"User action: Play video on device {device_id}")
    # Get the video
    video = video_service.get_video_by_id(play_request.video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with ID {play_request.video_id} not found",
        )
    
    # Get the device to determine the serve_ip
    device = device_service.get_device_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    
    # Use the direct video file path from the VideoModel
    video_path = video.path  # Access the path attribute directly
    if not video_path or not os.path.exists(video_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file for ID {play_request.video_id} not found: {video_path}",
        )
    
    logger.info(f"Playing video {video_path} on device {device_id} with loop={play_request.loop}")
    
    # Play the video on the device
    success = device_service.play_video(device_id, video_path, play_request.loop)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to play video on device with ID {device_id}",
        )
    
    # Trigger overlay sync if requested
    if sync_overlays:
        try:
            import requests
            response = requests.post(
                "http://localhost:8000/api/overlay/sync",
                params={
                    "triggered_by": "dlna_play",
                    "video_name": video.name
                },
                timeout=2  # Short timeout to not block play response
            )
            if response.status_code == 200:
                logger.info(f"Triggered overlay sync for video: {video.name}")
        except Exception as e:
            logger.error(f"Failed to sync overlays: {e}")
            # Don't fail the play operation if sync fails
    
    return {
        "success": True,
        "message": f"Video with ID {play_request.video_id} playing on device with ID {device_id}",
    }

@router.post("/{device_id}/stop", response_model=DeviceActionResponse)
def stop_video(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Stop playback on a device
    """
    success = device_service.stop_video(device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stop playback on device with ID {device_id}",
        )
    
    return {
        "success": True,
        "message": f"Playback stopped on device with ID {device_id}",
    }

@router.post("/{device_id}/pause", response_model=DeviceActionResponse)
def pause_video(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Pause playback on a device
    """
    success = device_service.pause_video(device_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause playback on device with ID {device_id}",
        )
    
    return {
        "success": True,
        "message": f"Playback paused on device with ID {device_id}",
    }

@router.post("/{device_id}/seek", response_model=DeviceActionResponse)
def seek_video(
    device_id: int,
    position: str = Query(..., description="Position to seek to (format: HH:MM:SS)"),
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Seek to a position in the current video
    """
    success = device_service.seek_video(device_id, position)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to seek on device with ID {device_id}",
        )
    
    return {
        "success": True,
        "message": f"Seeked to position {position} on device with ID {device_id}",
    }

@router.post("/{device_id}/update-progress", response_model=DeviceActionResponse)
def update_playback_progress(
    device_id: int,
    position: str = Query(..., description="Current playback position (format: HH:MM:SS)"),
    duration: str = Query(..., description="Total video duration (format: HH:MM:SS)"),
    progress: int = Query(..., description="Playback progress as a percentage (0-100)"),
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Update the playback progress for a device
    """
    # Get the device from the database
    device = device_service.get_device_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    
    # Update the playback progress
    success = device_service.update_playback_progress(device_id, position, duration, progress)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update playback progress for device with ID {device_id}",
        )

    return {
        "success": True,
        "message": f"Playback progress updated for device with ID {device_id}",
    }

# Move the discover endpoint to the top of the file, before the /{device_id} routes

@router.post("/load-config", response_model=DeviceList)
def load_devices_from_config(
    config_file: str = Query(..., description="Path to the configuration file"),
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Load devices from a configuration file
    """
    # Make sure the config file path is absolute
    if not os.path.isabs(config_file):
        config_file = os.path.abspath(config_file)
    
    # Check if the file exists
    if not os.path.exists(config_file):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Config file not found: {config_file}"
        )
    
    # Log the config file path
    logger.info(f"Loading devices from config file: {config_file}")
    
    devices = device_service.load_devices_from_config(config_file)
    return {
        "devices": devices,
        "total": len(devices),
    }

@router.post("/save-config", response_model=DeviceActionResponse)
def save_devices_to_config(
    config_file: str = Query(..., description="Path to the configuration file"),
    device_service: DeviceService = Depends(get_device_service),
):
    """
    Save devices to a configuration file
    """
    success = device_service.save_devices_to_config(config_file)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to save devices to config file {config_file}",
        )
    
    return {
        "success": True,
        "message": f"Devices saved to config file {config_file}",
    }


# User control mode endpoints
@router.post("/{device_id}/control/auto", response_model=DeviceActionResponse)
def enable_auto_mode(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """Enable automatic control mode for a device"""
    success = device_service.set_user_control(device_id, "auto", "user_enabled_auto")
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable auto mode for device {device_id}",
        )
    
    return {
        "success": True,
        "message": "Auto mode enabled",
    }

@router.post("/{device_id}/control/manual", response_model=DeviceActionResponse)
def enable_manual_mode(
    device_id: int,
    reason: str = Query("user_manual", description="Reason for manual mode"),
    expires_in: int = Query(None, description="Optional expiration in seconds"),
    device_service: DeviceService = Depends(get_device_service),
):
    """Enable manual control mode for a device"""
    success = device_service.set_user_control(device_id, "manual", reason, expires_in)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable manual mode for device {device_id}",
        )
    
    return {
        "success": True,
        "message": "Manual mode enabled",
    }

@router.get("/{device_id}/control")
def get_device_control_mode(
    device_id: int,
    device_service: DeviceService = Depends(get_device_service),
):
    """Get current control mode for a device"""
    device = device_service.get_device_by_id(device_id)
    if not device:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Device with ID {device_id} not found",
        )
    
    return {
        "mode": device.user_control_mode,
        "reason": device.user_control_reason,
        "expires_at": device.user_control_expires_at,
    }
