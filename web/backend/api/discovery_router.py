"""
API endpoints for the unified discovery system.
Provides REST APIs for device discovery, casting control, and configuration management.
"""

from fastapi import APIRouter, HTTPException, Depends, Query, Body
from sqlalchemy.orm import Session
from typing import List, Dict, Any, Optional
import asyncio
import logging

from database.database import get_db
from discovery.discovery_manager import DiscoveryManager
from discovery.config import ConfigurationManager
from discovery.base import CastingMethod, DeviceCapability
from services.app_runtime import get_app_runtime
from discovery.config.schema import (
    DeviceConfig, 
    GlobalConfig, 
    ConfigurationFile,
    validate_device_config,
    validate_global_config
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v2/discovery",
    tags=["discovery"],
    responses={404: {"description": "Not found"}}
)

config_manager = ConfigurationManager.get_instance()


def _get_discovery_manager() -> DiscoveryManager:
    try:
        return get_app_runtime().discovery_manager
    except Exception:
        return DiscoveryManager.get_instance()


# Device Discovery Endpoints

@router.get("/devices", response_model=List[Dict[str, Any]])
async def get_all_devices(
    casting_method: Optional[str] = Query(None, description="Filter by casting method"),
    online_only: bool = Query(False, description="Return only online devices"),
    group: Optional[str] = Query(None, description="Filter by device group"),
    zone: Optional[str] = Query(None, description="Filter by device zone")
):
    """Get all discovered devices with optional filters."""
    try:
        devices = _get_discovery_manager().get_all_devices()
        
        # Apply filters
        if casting_method:
            devices = [d for d in devices if d.casting_method.value == casting_method]
            
        if online_only:
            devices = [d for d in devices if d.is_online]
            
        if group:
            device_configs = config_manager.get_all_device_configs()
            group_devices = [name for name, config in device_configs.items() 
                           if config.get("group") == group]
            devices = [d for d in devices if d.name in group_devices]
            
        if zone:
            device_configs = config_manager.get_all_device_configs()
            zone_devices = [name for name, config in device_configs.items() 
                          if config.get("zone") == zone]
            devices = [d for d in devices if d.name in zone_devices]
        
        # Convert to dict for JSON serialization
        return [device.to_dict() for device in devices]
        
    except Exception as e:
        logger.error(f"Error getting devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/devices/{device_id}")
async def get_device(device_id: str):
    """Get details of a specific device."""
    try:
        device = _get_discovery_manager().get_device(device_id)
        if not device:
            raise HTTPException(status_code=404, detail="Device not found")
            
        return device.to_dict()
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device {device_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/discover")
async def trigger_discovery(
    backend: Optional[str] = Query(None, description="Specific backend to use"),
    timeout: int = Query(30, description="Discovery timeout in seconds")
):
    """Manually trigger device discovery."""
    try:
        # Run discovery
        devices = await _get_discovery_manager().discover_devices(
            backend_name=backend,
            timeout=timeout
        )
        
        return {
            "discovered": len(devices),
            "devices": [d.to_dict() for d in devices]
        }
        
    except Exception as e:
        logger.error(f"Error during discovery: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Casting Control Endpoints

@router.post("/cast")
async def cast_content(
    device_id: str = Body(..., description="Device ID to cast to"),
    content_url: str = Body(..., description="URL of content to cast"),
    content_type: str = Body("video/mp4", description="MIME type of content"),
    metadata: Optional[Dict[str, Any]] = Body(None, description="Additional metadata")
):
    """Cast content to a device."""
    try:
        session = await _get_discovery_manager().cast_content(
            device_id=device_id,
            content_url=content_url,
            content_type=content_type,
            metadata=metadata
        )
        
        if not session:
            raise HTTPException(status_code=400, detail="Failed to start casting")
            
        return {
            "session_id": session.session_id,
            "device_id": session.device_id,
            "status": "started"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error casting content: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stop/{device_id}")
async def stop_casting(device_id: str):
    """Stop casting on a device."""
    try:
        success = await _get_discovery_manager().stop_casting(device_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to stop casting")
            
        return {"status": "stopped", "device_id": device_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error stopping cast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/pause/{device_id}")
async def pause_casting(device_id: str):
    """Pause casting on a device."""
    try:
        success = await _get_discovery_manager().pause_casting(device_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to pause casting")
            
        return {"status": "paused", "device_id": device_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing cast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/resume/{device_id}")
async def resume_casting(device_id: str):
    """Resume casting on a device."""
    try:
        success = await _get_discovery_manager().resume_casting(device_id)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to resume casting")
            
        return {"status": "resumed", "device_id": device_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming cast: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sessions")
async def get_active_sessions():
    """Get all active casting sessions."""
    try:
        sessions = _get_discovery_manager().get_active_sessions()
        
        return {
            "total": len(sessions),
            "sessions": [s.to_dict() for s in sessions]
        }
        
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Configuration Endpoints

@router.get("/config/devices")
async def get_device_configs():
    """Get all device configurations."""
    try:
        configs = config_manager.get_all_device_configs()
        return configs
        
    except Exception as e:
        logger.error(f"Error getting device configs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/devices/{device_name}")
async def get_device_config(device_name: str):
    """Get configuration for a specific device."""
    try:
        config = config_manager.get_device_config(device_name)
        
        if not config:
            raise HTTPException(status_code=404, detail="Device configuration not found")
            
        return config
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/devices/{device_name}")
async def update_device_config(
    device_name: str,
    config: Dict[str, Any] = Body(..., description="Device configuration")
):
    """Update configuration for a device."""
    try:
        # Ensure name matches
        config["name"] = device_name
        
        # Validate configuration
        valid_config = validate_device_config(config)
        if not valid_config:
            raise HTTPException(status_code=400, detail="Invalid device configuration")
            
        success = config_manager.update_device_config(device_name, config)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update configuration")
            
        return {"status": "updated", "device": device_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/config/devices/{device_name}")
async def delete_device_config(device_name: str):
    """Delete configuration for a device."""
    try:
        success = config_manager.remove_device_config(device_name)
        
        if not success:
            raise HTTPException(status_code=404, detail="Device configuration not found")
            
        return {"status": "deleted", "device": device_name}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting device config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/config/global")
async def get_global_config():
    """Get global configuration."""
    try:
        config = config_manager.get_global_config()
        return config
        
    except Exception as e:
        logger.error(f"Error getting global config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/config/global")
async def update_global_config(
    config: Dict[str, Any] = Body(..., description="Global configuration updates")
):
    """Update global configuration."""
    try:
        # Validate configuration
        valid_config = validate_global_config(config)
        if not valid_config:
            raise HTTPException(status_code=400, detail="Invalid global configuration")
            
        success = config_manager.update_global_config(config)
        
        if not success:
            raise HTTPException(status_code=400, detail="Failed to update configuration")
            
        return {"status": "updated"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error updating global config: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Backend Management Endpoints

@router.get("/backends")
async def get_backends():
    """Get information about all registered discovery backends."""
    try:
        status = _get_discovery_manager().get_backend_status()
        return status
        
    except Exception as e:
        logger.error(f"Error getting backend status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backends/{backend_name}/enable")
async def enable_backend(backend_name: str):
    """Enable a discovery backend."""
    try:
        # Update global config
        current_config = config_manager.get_global_config()
        if "backends" not in current_config:
            current_config["backends"] = {}
            
        current_config["backends"][backend_name] = True
        config_manager.update_global_config(current_config)
        
        # Re-register backend if needed
        await _get_discovery_manager()._register_enabled_backends()
        
        return {"status": "enabled", "backend": backend_name}
        
    except Exception as e:
        logger.error(f"Error enabling backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/backends/{backend_name}/disable")
async def disable_backend(backend_name: str):
    """Disable a discovery backend."""
    try:
        # Update global config
        current_config = config_manager.get_global_config()
        if "backends" not in current_config:
            current_config["backends"] = {}
            
        current_config["backends"][backend_name] = False
        config_manager.update_global_config(current_config)
        
        # Unregister backend
        _get_discovery_manager().unregister_backend(backend_name)
        
        return {"status": "disabled", "backend": backend_name}
        
    except Exception as e:
        logger.error(f"Error disabling backend: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# System Status Endpoints

@router.get("/status")
async def get_system_status():
    """Get overall discovery system status."""
    try:
        discovery_manager = _get_discovery_manager()
        discovery_status = discovery_manager.get_backend_status()
        device_count = len(discovery_manager.get_all_devices())
        online_count = len([d for d in discovery_manager.get_all_devices() if d.is_online])
        session_count = len(discovery_manager.get_active_sessions())
        
        return {
            "discovery_running": discovery_manager.is_running,
            "total_devices": device_count,
            "online_devices": online_count,
            "active_sessions": session_count,
            "backends": discovery_status
        }
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/capabilities")
async def get_capabilities():
    """Get supported casting methods and device capabilities."""
    return {
        "casting_methods": [method.value for method in CastingMethod],
        "device_capabilities": [cap.value for cap in DeviceCapability],
        "content_types": [
            "video/mp4",
            "audio/mp3", 
            "image/jpeg",
            "text/html",
            "application/x-mpegURL"
        ]
    }


# Health Check

@router.get("/health")
async def health_check():
    """Check health of discovery system."""
    try:
        discovery_manager = _get_discovery_manager()
        is_healthy = discovery_manager.is_running
        backend_status = discovery_manager.get_backend_status()
        
        # Check if at least one backend is active
        has_active_backend = any(b["active"] for b in backend_status.values())
        
        if not is_healthy or not has_active_backend:
            raise HTTPException(status_code=503, detail="Discovery system unhealthy")
            
        return {
            "status": "healthy",
            "discovery_running": is_healthy,
            "backends_active": has_active_backend
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        raise HTTPException(status_code=503, detail=str(e))
