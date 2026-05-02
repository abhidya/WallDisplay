"""
Renderer Service router.

This module provides the FastAPI router for the Renderer Service.
"""

import logging
from typing import Dict, Any, List, Optional, Union

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from web.backend.core.renderer_service.service import RendererService
from web.backend.core.renderer_service.sender.airplay_discovery import AirPlayDiscovery


# Define the request and response models
class RendererStartRequest(BaseModel):
    """Request model for starting a renderer."""
    scene: str
    projector: str
    options: Optional[Dict[str, Any]] = None


class RendererStopRequest(BaseModel):
    """Request model for stopping a renderer."""
    projector: str


class RendererStatusRequest(BaseModel):
    """Request model for getting renderer status."""
    projector: str


class ProjectorStartRequest(BaseModel):
    """Request model for starting a projector."""
    projector_id: Optional[str] = None


class RendererResponse(BaseModel):
    """Response model for renderer operations."""
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None


# Create the router
router = APIRouter(
    prefix="/renderer",
    tags=["renderer"],
    responses={404: {"description": "Not found"}},
)

# Create a logger
logger = logging.getLogger(__name__)

# Create the Renderer Service
renderer_service = RendererService()

def get_renderer_service():
    """
    Get the renderer service instance.
    
    Returns:
        RendererService instance
    """
    return renderer_service


@router.post("/start", response_model=RendererResponse)
async def start_renderer(request: RendererStartRequest):
    """
    Start a renderer for a scene on a projector.
    
    Args:
        request: Request model containing scene and projector IDs
        
    Returns:
        Response model with success status, message, and data
    """
    try:
        success = renderer_service.start_renderer(request.scene, request.projector)
        
        if success:
            return RendererResponse(
                success=True,
                message=f"Started renderer for scene {request.scene} on projector {request.projector}",
                data=renderer_service.get_renderer_status(request.projector)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start renderer for scene {request.scene} on projector {request.projector}"
            )
            
    except Exception as e:
        logger.error(f"Error starting renderer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error starting renderer: {str(e)}"
        )


@router.post("/stop", response_model=RendererResponse)
async def stop_renderer(request: RendererStopRequest):
    """
    Stop a renderer on a projector.
    
    Args:
        request: Request model containing projector ID
        
    Returns:
        Response model with success status, message, and data
    """
    try:
        success = renderer_service.stop_renderer(request.projector)
        
        if success:
            return RendererResponse(
                success=True,
                message=f"Stopped renderer on projector {request.projector}",
                data=None
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to stop renderer on projector {request.projector}"
            )
            
    except Exception as e:
        logger.error(f"Error stopping renderer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error stopping renderer: {str(e)}"
        )


@router.get("/status/{projector_id}", response_model=RendererResponse)
async def get_renderer_status(projector_id: str):
    """
    Get the status of a renderer on a projector.
    
    Args:
        projector_id: ID of the projector
        
    Returns:
        Response model with success status, message, and data
    """
    try:
        status = renderer_service.get_renderer_status(projector_id)
        
        if status:
            return RendererResponse(
                success=True,
                message=f"Got renderer status for projector {projector_id}",
                data=status
            )
        else:
            return RendererResponse(
                success=True,
                message=f"No active renderer found for projector {projector_id}",
                data=None
            )
            
    except Exception as e:
        logger.error(f"Error getting renderer status: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting renderer status: {str(e)}"
        )


@router.get("/list", response_model=RendererResponse)
async def list_renderers():
    """
    List all active renderers.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        renderers = renderer_service.list_active_renderers()
        
        return RendererResponse(
            success=True,
            message=f"Listed {len(renderers)} active renderers",
            data={"renderers": renderers}
        )
            
    except Exception as e:
        logger.error(f"Error listing renderers: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing renderers: {str(e)}"
        )


@router.get("/projectors", response_model=RendererResponse)
async def list_projectors():
    """
    List all available projectors.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        projectors_dict = renderer_service.config.get('projectors', {})
        
        # Transform the dictionary into a list of projector objects with id field
        projectors_list = []
        for proj_id, proj_data in projectors_dict.items():
            # Create a copy of the projector data
            projector = dict(proj_data)
            # Add the id field
            projector['id'] = proj_id
            projectors_list.append(projector)
        
        return RendererResponse(
            success=True,
            message=f"Listed {len(projectors_list)} projectors",
            data={"projectors": projectors_list}
        )
            
    except Exception as e:
        logger.error(f"Error listing projectors: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing projectors: {str(e)}"
        )


@router.get("/scenes", response_model=RendererResponse)
async def list_scenes():
    """
    List all available scenes.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        scenes_dict = renderer_service.config.get('scenes', {})
        
        # Transform the dictionary into a list of scene objects with id field
        scenes_list = []
        for scene_id, scene_data in scenes_dict.items():
            # Create a copy of the scene data
            scene = dict(scene_data)
            # Add the id and name fields
            scene['id'] = scene_id
            # If name is not provided, use the ID as the name
            if 'name' not in scene:
                scene['name'] = scene_id
            scenes_list.append(scene)
        
        return RendererResponse(
            success=True,
            message=f"Listed {len(scenes_list)} scenes",
            data={"scenes": scenes_list}
        )
            
    except Exception as e:
        logger.error(f"Error listing scenes: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing scenes: {str(e)}"
        )


@router.post("/start_projector", response_model=RendererResponse)
async def start_projector(
    projector_id: str = None, 
    request: ProjectorStartRequest = None
):
    """
    Start a projector with its default scene.
    
    Args:
        projector_id: ID of the projector (from query parameter)
        request: Request model containing projector ID (from request body)
        
    Returns:
        Response model with success status, message, and data
    """
    # If projector_id is not provided in query params, try to get it from the request body
    if projector_id is None and request is not None:
        projector_id = request.projector_id
    
    if not projector_id:
        raise HTTPException(
            status_code=400,
            detail="projector_id is required either as a query parameter or in the request body"
        )
    try:
        # Get the projector configuration
        projector_config = renderer_service.get_projector_config(projector_id)
        if not projector_config:
            raise HTTPException(
                status_code=404,
                detail=f"Projector not found: {projector_id}"
            )
        
        # Get the scene ID from the projector configuration
        scene_id = projector_config.get('scene')
        if not scene_id:
            raise HTTPException(
                status_code=400,
                detail=f"No default scene configured for projector {projector_id}"
            )
        
        # Start the renderer
        success = renderer_service.start_renderer(scene_id, projector_id)
        
        if success:
            return RendererResponse(
                success=True,
                message=f"Started projector {projector_id} with scene {scene_id}",
                data=renderer_service.get_renderer_status(projector_id)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to start projector {projector_id} with scene {scene_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting projector: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error starting projector: {str(e)}"
        )


@router.get("/airplay/discover", response_model=RendererResponse)
async def discover_airplay_devices():
    """
    Discover AirPlay devices on the network.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        # Create an AirPlay discovery instance
        airplay_discovery = AirPlayDiscovery(logger=logger)
        
        # Discover devices
        devices = airplay_discovery.discover_devices()
        
        return RendererResponse(
            success=True,
            message=f"Discovered {len(devices)} AirPlay devices",
            data={"devices": devices}
        )
            
    except Exception as e:
        logger.error(f"Error discovering AirPlay devices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error discovering AirPlay devices: {str(e)}"
        )


@router.get("/airplay/list", response_model=RendererResponse)
async def list_airplay_devices():
    """
    List AirPlay devices available in System Preferences.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        # Create an AirPlay discovery instance
        airplay_discovery = AirPlayDiscovery(logger=logger)
        
        # List devices from System Preferences
        devices = airplay_discovery.list_devices_from_system_prefs()
        
        return RendererResponse(
            success=True,
            message=f"Found {len(devices)} AirPlay devices in System Preferences",
            data={"devices": devices}
        )
            
    except Exception as e:
        logger.error(f"Error listing AirPlay devices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error listing AirPlay devices: {str(e)}"
        )


@router.post("/pause/{projector_id}", response_model=RendererResponse)
async def pause_renderer(projector_id: str):
    """
    Pause a renderer on a projector.
    
    Args:
        projector_id: ID of the projector
        
    Returns:
        Response model with success status, message, and data
    """
    try:
        # Use the RendererService's pause_renderer method
        success = renderer_service.pause_renderer(projector_id)
        
        if success:
            return RendererResponse(
                success=True,
                message=f"Paused renderer on projector {projector_id}",
                data=renderer_service.get_renderer_status(projector_id)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to pause renderer on projector {projector_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error pausing renderer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error pausing renderer: {str(e)}"
        )


@router.post("/resume/{projector_id}", response_model=RendererResponse)
async def resume_renderer(projector_id: str):
    """
    Resume a paused renderer on a projector.
    
    Args:
        projector_id: ID of the projector
        
    Returns:
        Response model with success status, message, and data
    """
    try:
        # Use the RendererService's resume_renderer method
        success = renderer_service.resume_renderer(projector_id)
        
        if success:
            return RendererResponse(
                success=True,
                message=f"Resumed renderer on projector {projector_id}",
                data=renderer_service.get_renderer_status(projector_id)
            )
        else:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to resume renderer on projector {projector_id}"
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error resuming renderer: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error resuming renderer: {str(e)}"
        )


@router.get("/airplay/devices", response_model=RendererResponse)
async def get_airplay_devices():
    """
    Get all AirPlay devices using both discovery methods.
    
    Returns:
        Response model with success status, message, and data
    """
    try:
        # Create an AirPlay discovery instance
        airplay_discovery = AirPlayDiscovery(logger=logger)
        
        # Get all devices
        devices = airplay_discovery.get_devices()
        
        return RendererResponse(
            success=True,
            message=f"Found {len(devices)} AirPlay devices",
            data={"devices": devices}
        )
            
    except Exception as e:
        logger.error(f"Error getting AirPlay devices: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Error getting AirPlay devices: {str(e)}"
        )
