from fastapi import APIRouter, HTTPException, Depends, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import json
import uuid
from datetime import datetime
import asyncio
from pydantic import BaseModel

from database.database import get_db
from schemas.overlay import (
    ApiConfigs,
    OverlayConfigCreate,
    OverlayConfigUpdate,
    OverlayConfigResponse,
    OverlayStreamRequest,
    OverlayStreamResponse,
    OverlayWindowInitResponse,
    OverlayCastStartRequest,
    OverlayCastSessionResponse,
)
from services.overlay_service import OverlayService
from services.overlay_cast_service import get_overlay_cast_service
from services.overlay_event_bus import overlay_events, notify_overlay_config_update
from models.overlay import OverlayConfig

router = APIRouter(prefix="/api/overlay", tags=["overlay"])


class ProjectorRedirectConfigPayload(BaseModel):
    enabled: bool = False
    client_ip: str = ""
    target_path: str = "/backend-static/overlay_window.html?config_id=5&controls=hidden"

@router.post("/configs", response_model=OverlayConfigResponse)
async def create_overlay_config(
    config: OverlayConfigCreate,
    db: Session = Depends(get_db)
):
    """Create a new overlay configuration"""
    try:
        service = OverlayService(db)
        new_config = service.create_config(config)
        notify_overlay_config_update([new_config.id], "overlay_config_created")
        return new_config
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configs", response_model=List[OverlayConfigResponse])
async def list_overlay_configs(
    video_id: Optional[int] = Query(None, description="Filter by video ID"),
    mapping_scene_id: Optional[int] = Query(None, description="Filter by mapping scene ID"),
    db: Session = Depends(get_db)
):
    """List overlay configurations, optionally filtered by video ID"""
    try:
        service = OverlayService(db)
        configs = service.list_configs(video_id=video_id)
        if mapping_scene_id is not None:
            configs = [config for config in configs if config.mapping_scene_id == mapping_scene_id]
        return configs
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/configs/{config_id}", response_model=OverlayConfigResponse)
async def get_overlay_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """Get a specific overlay configuration"""
    try:
        service = OverlayService(db)
        config = service.get_config(config_id)
        if not config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        return config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.put("/configs/{config_id}", response_model=OverlayConfigResponse)
async def update_overlay_config(
    config_id: int,
    config_update: OverlayConfigUpdate,
    db: Session = Depends(get_db)
):
    """Update an overlay configuration"""
    try:
        service = OverlayService(db)
        updated_config = service.update_config(config_id, config_update)
        if not updated_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        notify_overlay_config_update([updated_config.id], "overlay_config_updated")
        return updated_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/configs/{config_id}")
async def delete_overlay_config(
    config_id: int,
    db: Session = Depends(get_db)
):
    """Delete an overlay configuration"""
    try:
        service = OverlayService(db)
        success = service.delete_config(config_id)
        if not success:
            raise HTTPException(status_code=404, detail="Configuration not found")
        return {"message": "Configuration deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/configs/{config_id}/duplicate", response_model=OverlayConfigResponse)
async def duplicate_overlay_config(
    config_id: int,
    new_name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Duplicate an overlay configuration"""
    try:
        service = OverlayService(db)
        new_config = service.duplicate_config(config_id, new_name)
        if not new_config:
            raise HTTPException(status_code=404, detail="Configuration not found")
        return new_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/stream", response_model=OverlayStreamResponse)
async def create_overlay_stream(
    stream_request: OverlayStreamRequest,
    db: Session = Depends(get_db)
):
    """Create a streaming URL for overlay projection"""
    try:
        service = OverlayService(db)
        stream_info = service.create_stream(stream_request.video_id, stream_request.config_id)
        return stream_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/window-init", response_model=OverlayWindowInitResponse)
async def get_overlay_window_init(
    config_id: int = Query(..., description="Overlay configuration ID"),
    db: Session = Depends(get_db)
):
    """Build a self-contained payload for bootstrapping overlay_window.html via URL params."""
    try:
        service = OverlayService(db)
        return service.get_window_init_payload(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/window-refresh-state")
async def get_overlay_window_refresh_state(
    config_id: int = Query(..., description="Overlay configuration ID"),
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        return service.get_window_refresh_state(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/widget-data")
async def get_overlay_widget_data(
    config_id: int = Query(..., description="Overlay configuration ID"),
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        return service.get_live_widget_data(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/global-api-configs")
async def get_global_api_configs(
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        return service.get_global_api_configs()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/global-api-configs")
async def update_global_api_configs(
    api_configs: ApiConfigs,
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        updated = service.update_global_api_configs(api_configs.model_dump())
        config_ids = [config_id for (config_id,) in db.query(OverlayConfig.id).all()]
        notify_overlay_config_update(config_ids, "overlay_global_api_configs_updated")
        return updated
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/projector-redirect")
async def get_projector_redirect_config(
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        return service.get_projector_redirect_config()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.put("/projector-redirect")
async def update_projector_redirect_config(
    payload: ProjectorRedirectConfigPayload,
    db: Session = Depends(get_db)
):
    try:
        service = OverlayService(db)
        return service.update_projector_redirect_config(payload.model_dump())
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/cast", response_model=OverlayCastSessionResponse)
async def start_overlay_cast(
    cast_request: OverlayCastStartRequest,
    request: Request,
):
    """Launch a headless overlay capture session and relay MPEG-TS over DLNA."""
    try:
        service = get_overlay_cast_service()
        overlay_base_url = cast_request.overlay_base_url or str(request.base_url).rstrip("/")
        session = await service.start_cast(
            device_id=cast_request.device_id,
            config_id=cast_request.config_id,
            overlay_base_url=overlay_base_url,
            controls_hidden=cast_request.controls_hidden,
            viewport_width=cast_request.viewport_width,
            viewport_height=cast_request.viewport_height,
            capture_width=cast_request.capture_width,
            capture_height=cast_request.capture_height,
            quality=cast_request.quality,
            frame_rate=cast_request.frame_rate,
            stream_port=cast_request.stream_port,
        )
        return OverlayCastSessionResponse(**session)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("/cast/sessions", response_model=List[OverlayCastSessionResponse])
async def list_overlay_cast_sessions():
    service = get_overlay_cast_service()
    return [OverlayCastSessionResponse(**session) for session in service.list_sessions()]


@router.delete("/cast/sessions/{session_id}")
async def stop_overlay_cast(session_id: str):
    service = get_overlay_cast_service()
    stopped = await service.stop_cast(session_id)
    if not stopped:
        raise HTTPException(status_code=404, detail="Overlay cast session not found")
    return {"status": "stopped", "session_id": session_id}

@router.get("/templates", response_model=List[OverlayConfigResponse])
async def list_overlay_templates():
    """Get available overlay configuration templates"""
    templates = [
        {
            "id": -1,
            "name": "Weather & Time Display",
            "video_id": None,
            "video_transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0},
            "widgets": [
                {
                    "id": "weather-1",
                    "type": "weather",
                    "position": {"x": 50, "y": 50},
                    "size": {"width": 400, "height": 200},
                    "config": {"city": "San Francisco", "units": "metric"},
                    "visible": True
                },
                {
                    "id": "time-1",
                    "type": "time",
                    "position": {"x": 1470, "y": 50},
                    "size": {"width": 300, "height": 100},
                    "config": {"format": "24h", "showSeconds": True},
                    "visible": True
                },
                {
                    "id": "lights-1",
                    "type": "lights",
                    "position": {"x": 50, "y": 950},
                    "size": {"width": 120, "height": 60},
                    "config": {},
                    "visible": True
                }
            ],
            "api_configs": {
                "weather_api_key": "",
                "timezone": "America/Los_Angeles"
            },
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        },
        {
            "id": -2,
            "name": "Transit Information Board",
            "video_id": None,
            "video_transform": {"x": 0, "y": 0, "scale": 1, "rotation": 0},
            "widgets": [
                {
                    "id": "time-1",
                    "type": "time",
                    "position": {"x": 760, "y": 50},
                    "size": {"width": 400, "height": 150},
                    "config": {"format": "12h", "showSeconds": False},
                    "visible": True
                },
                {
                    "id": "transit-1",
                    "type": "transit",
                    "position": {"x": 50, "y": 300},
                    "size": {"width": 600, "height": 400},
                    "config": {"stopName": "Main Station", "routeFilter": ""},
                    "visible": True
                },
                {
                    "id": "transit-2",
                    "type": "transit",
                    "position": {"x": 1270, "y": 300},
                    "size": {"width": 600, "height": 400},
                    "config": {"stopName": "Secondary Station", "routeFilter": ""},
                    "visible": True
                }
            ],
            "api_configs": {
                "transit_stop_id": "13915",
                "timezone": "America/Los_Angeles"
            },
            "created_at": datetime.utcnow().isoformat(),
            "updated_at": datetime.utcnow().isoformat()
        }
    ]
    return templates

@router.post("/configs/from-template/{template_id}", response_model=OverlayConfigResponse)
async def create_config_from_template(
    template_id: int,
    video_id: int,
    name: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Create a new overlay configuration from a template"""
    try:
        # Get templates
        templates = await list_overlay_templates()
        template = next((t for t in templates if t["id"] == template_id), None)
        
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")
        
        # Create new config from template
        config_data = OverlayConfigCreate(
            name=name or f"{template['name']} - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            video_id=video_id,
            video_transform=template["video_transform"],
            widgets=template["widgets"],
            api_configs=template["api_configs"]
        )
        
        service = OverlayService(db)
        new_config = service.create_config(config_data)
        return new_config
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Simple in-memory brightness storage for smart light integration
brightness_state = {"value": 100}  # Default 100 = lights on (no darkening)

# Simple in-memory sync state for overlay synchronization
sync_state = {
    "event_id": None,
    "timestamp": None,
    "triggered_by": None,
    "video_name": None
}

@router.get("/brightness")
async def get_brightness():
    """Get current brightness value for smart light integration and DLNA control status"""
    try:
        from services.brightness_control_service import get_brightness_control_service
        
        brightness_service = get_brightness_control_service()
        status = brightness_service.get_status()
        
        return {
            "brightness": brightness_state["value"],
            "dlna_control": status
        }
    except ImportError:
        # Fallback if brightness control service is not available
        return {
            "brightness": brightness_state["value"],
            "dlna_control": {
                "blackout_active": False,
                "error": "Brightness control service not available"
            }
        }

@router.post("/brightness")
async def set_brightness(brightness: int = Query(..., ge=0, le=100)):
    """Set brightness value (0-100) for smart light integration and DLNA device control
    0 = lights off (black screen) - casts black video to all playing DLNA devices
    1-100 = lights on - restores original videos on DLNA devices
    """
    old_brightness = brightness_state["value"]
    brightness_state["value"] = brightness
    
    # Broadcast brightness change to SSE clients
    if old_brightness != brightness:
        asyncio.create_task(overlay_events.broadcast("brightness", {"brightness": brightness}))
    
    try:
        from services.brightness_control_service import get_brightness_control_service
        
        # Control DLNA devices based on brightness
        brightness_service = get_brightness_control_service()
        result = brightness_service.set_brightness(brightness)
        
        # Merge the results
        return {
            "brightness": brightness,
            "status": result.get("status", "updated"),
            **result
        }
    except Exception as e:
        # Log the error for debugging
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to use brightness control service: {e}", exc_info=True)
        
        # Return basic response without DLNA control
        return {
            "brightness": brightness,
            "status": "updated",
            "message": "Brightness updated (DLNA control not available)",
            "error": str(e)
        }

@router.post("/sync")
async def trigger_sync(
    triggered_by: str = Query("manual", description="Source of sync trigger"),
    video_name: Optional[str] = Query(None, description="Name of video being played")
):
    """Trigger sync for all overlay sessions and DLNA devices"""
    event_id = str(uuid.uuid4())[:8]
    
    sync_state.update({
        "event_id": event_id,
        "timestamp": datetime.utcnow().isoformat(),
        "triggered_by": triggered_by,
        "video_name": video_name
    })
    
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Overlay sync triggered: {triggered_by} - {video_name} - {event_id}")
    
    # Broadcast sync event to SSE clients
    asyncio.create_task(overlay_events.broadcast("sync", {
        "event_id": event_id,
        "timestamp": sync_state["timestamp"],
        "triggered_by": triggered_by,
        "video_name": video_name
    }))
    
    # Sync DLNA devices to 00:00:00
    synced_devices = []
    failed_devices = []
    try:
        from services.app_runtime import get_app_runtime

        for device in get_app_runtime().get_devices():
            if device.is_playing:
                try:
                    if device.seek("00:00:00"):
                        synced_devices.append(device.name)
                        logger.info(f"Successfully synced DLNA device: {device.name}")
                    else:
                        failed_devices.append(device.name)
                        logger.warning(f"Failed to sync DLNA device: {device.name}")
                except Exception as e:
                    failed_devices.append(device.name)
                    logger.error(f"Error syncing DLNA device {device.name}: {e}")
    except Exception as e:
        logger.error(f"Error accessing device manager for sync: {e}")
    
    return {
        "status": "sync triggered",
        "event_id": event_id,
        "affected_overlays": "all",
        "synced_devices": synced_devices,
        "failed_devices": failed_devices,
        "device_count": len(synced_devices)
    }

@router.get("/status")
async def get_overlay_status():
    """Combined status endpoint for overlay windows"""
    return {
        "brightness": brightness_state["value"],
        "sync": sync_state,
        "server_time": datetime.utcnow().isoformat()
    }


@router.get("/playback-sync")
async def get_overlay_playback_sync(
    config_id: int = Query(..., description="Overlay configuration id"),
    db: Session = Depends(get_db),
):
    try:
        service = OverlayService(db)
        return service.get_mapping_playback_sync(config_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc

@router.get("/brightness/status")
async def get_brightness_status():
    """Get detailed brightness and DLNA control status"""
    from services.brightness_control_service import get_brightness_control_service
    
    brightness_service = get_brightness_control_service()
    status = brightness_service.get_status()
    
    return {
        "brightness": brightness_state["value"],
        "dlna_control": status,
        "description": {
            "blackout_active": "Whether blackout mode is currently active (brightness = 0)",
            "black_video_available": "Whether the black video file is available",
            "playing_devices": "List of currently playing devices and their content",
            "backed_up_devices": "Devices whose state was saved before blackout",
            "total_devices": "Total number of DLNA devices",
            "playing_count": "Number of devices currently playing"
        }
    }

@router.get("/events")
async def overlay_events_stream():
    """Server-Sent Events endpoint for real-time overlay updates"""
    queue = await overlay_events.connect()
    
    async def event_generator():
        try:
            # Send initial state
            initial_data = {
                "type": "init",
                "data": {
                    "brightness": brightness_state["value"],
                    "sync": sync_state
                }
            }
            yield f"data: {json.dumps(initial_data)}\n\n"
            
            # Send updates as they occur
            while True:
                try:
                    # Wait for events with timeout to detect disconnections
                    event = await asyncio.wait_for(queue.get(), timeout=30.0)
                    yield f"data: {json.dumps(event)}\n\n"
                except asyncio.TimeoutError:
                    # Send heartbeat to keep connection alive
                    yield ": heartbeat\n\n"
                    
        except asyncio.CancelledError:
            # Client disconnected
            pass
        finally:
            overlay_events.disconnect(queue)
    
    return StreamingResponse(
        event_generator(), 
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable nginx buffering
        }
    )
