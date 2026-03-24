"""
API endpoints for streaming session management.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, HTTPException, Path, Depends
from typing import Dict, Any, List, Optional
import asyncio
import logging
import json
import os

# Fix the import causing startup errors
from core.streaming_registry import StreamingSessionRegistry
from core.device_manager import DeviceManager, get_device_manager # Import get_device_manager
from core.twisted_streaming import get_instance as get_twisted_streaming
from services.device_service import DeviceService # Import DeviceService class
# DO NOT Import get_device_service from services.device_service
from services.video_service import VideoService, get_video_service # This is fine
from database.database import get_db
from sqlalchemy.orm import Session # Import Session for type hinting

router = APIRouter(
    prefix="/streaming",
    tags=["streaming"],
    responses={404: {"description": "Not found"}},
)

# Add logger
logger = logging.getLogger(__name__)

# Dependency to get the device service, defined locally
def get_device_service_local(db: Session = Depends(get_db)) -> DeviceService:
    # Use get_device_manager to obtain the singleton instance
    device_manager_instance = get_device_manager()
    return DeviceService(db, device_manager_instance)

@router.get("/")
async def get_streaming_stats() -> Dict[str, Any]:
    """
    Get streaming system statistics
    
    Returns:
        Dict[str, Any]: Statistics about streaming sessions
    """
    registry = StreamingSessionRegistry.get_instance()
    return registry.get_streaming_stats()

@router.post("/start", response_model=Dict[str, Any])
async def start_streaming(
    device_id: int,
    video_path: str,
    device_service: DeviceService = Depends(get_device_service_local) # Use local version
) -> Dict[str, Any]:
    """
    Start streaming a video to a device
    
    Args:
        device_id: ID of the device to stream to
        video_path: Path to the video file
        
    Returns:
        Dict[str, Any]: Streaming information
    """
    logger.info(f"Starting streaming for device {device_id} with video {video_path}")
    
    # Check if the video file exists
    if not os.path.exists(video_path):
        raise HTTPException(status_code=404, detail=f"Video file not found: {video_path}")
    
    # Play the video using device service (which will use the Twisted streaming)
    success = device_service.play_video(device_id, video_path, loop=True)
    
    if not success:
        raise HTTPException(status_code=500, detail=f"Failed to start streaming")
    
    return {"status": "success", "message": f"Streaming started for device {device_id}"}

@router.get("/sessions")
async def get_all_sessions() -> List[Dict[str, Any]]:
    """
    Get all streaming sessions
    
    Returns:
        List[Dict[str, Any]]: List of all sessions
    """
    registry = StreamingSessionRegistry.get_instance()
    sessions = registry.get_active_sessions()
    return [session.to_dict() for session in sessions]

@router.get("/sessions/{session_id}")
async def get_session(session_id: str) -> Dict[str, Any]:
    """
    Get a specific streaming session
    
    Args:
        session_id: ID of the session to get
        
    Returns:
        Dict[str, Any]: Session information
        
    Raises:
        HTTPException: If session not found
    """
    registry = StreamingSessionRegistry.get_instance()
    session = registry.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
        
    return session.to_dict()

@router.delete("/sessions/{session_id}")
async def delete_session(session_id: str) -> Dict[str, Any]:
    """
    Force-remove a streaming session from the registry.

    Args:
        session_id: ID of the session to remove

    Returns:
        Dict[str, Any]: Action status

    Raises:
        HTTPException: If session not found
    """
    registry = StreamingSessionRegistry.get_instance()
    removed = registry.unregister_session(session_id)
    if not removed:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    return {"status": "success", "message": f"Session {session_id} removed"}

@router.get("/device/{device_name}")
async def get_sessions_for_device(device_name: str) -> List[Dict[str, Any]]:
    """
    Get streaming sessions for a specific device
    
    Args:
        device_name: Name of the device
        
    Returns:
        List[Dict[str, Any]]: List of sessions for the device
    """
    registry = StreamingSessionRegistry.get_instance()
    sessions = registry.get_sessions_for_device(device_name)
    return [session.to_dict() for session in sessions]
    
@router.post("/sessions/{session_id}/complete")
async def complete_session(session_id: str) -> Dict[str, Any]:
    """
    Mark a streaming session as completed
    
    Args:
        session_id: ID of the session to complete
        
    Returns:
        Dict[str, Any]: Session information
        
    Raises:
        HTTPException: If session not found
    """
    registry = StreamingSessionRegistry.get_instance()
    session = registry.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    session.complete()
    return {"status": "success", "message": f"Session {session_id} marked as completed"}

@router.post("/sessions/{session_id}/reset")
async def reset_session(session_id: str) -> Dict[str, Any]:
    """
    Reset a streaming session to active state
    
    Args:
        session_id: ID of the session to reset
        
    Returns:
        Dict[str, Any]: Session information
        
    Raises:
        HTTPException: If session not found
    """
    registry = StreamingSessionRegistry.get_instance()
    session = registry.get_session(session_id)
    
    if not session:
        raise HTTPException(status_code=404, detail=f"Session {session_id} not found")
    
    session.status = "active"
    session.update_activity()
    return {"status": "success", "message": f"Session {session_id} reset to active status"}

@router.get("/analytics")
async def get_streaming_analytics() -> Dict[str, Any]:
    """
    Get detailed streaming analytics
    
    Returns:
        Dict[str, Any]: Detailed analytics about streaming sessions
    """
    registry = StreamingSessionRegistry.get_instance()
    stats = registry.get_streaming_stats()
    
    # Add more detailed analytics
    active_sessions = registry.get_active_sessions()
    
    # Calculate total bandwidth
    total_bandwidth = sum(session.get_bandwidth() for session in active_sessions)
    bandwidth_by_stream_type: Dict[str, float] = {}
    active_by_stream_type: Dict[str, int] = {}
    active_by_consumer_prefix: Dict[str, int] = {}

    for session in active_sessions:
        bandwidth_by_stream_type[session.stream_type] = (
            bandwidth_by_stream_type.get(session.stream_type, 0) + session.get_bandwidth()
        )
        active_by_stream_type[session.stream_type] = active_by_stream_type.get(session.stream_type, 0) + 1
        consumer_prefix = (session.consumer_id or "unassigned").split(":", 1)[0]
        active_by_consumer_prefix[consumer_prefix] = active_by_consumer_prefix.get(consumer_prefix, 0) + 1
    
    # Count connection events
    connection_events = sum(len(session.connection_history) for session in active_sessions)
    
    # Calculate average uptime
    if active_sessions:
        avg_uptime = sum((session.last_activity_time - session.start_time).total_seconds() 
                         for session in active_sessions) / len(active_sessions)
    else:
        avg_uptime = 0
    
    # Add to stats
    stats.update({
        "total_bandwidth_bps": total_bandwidth,
        "bandwidth_by_stream_type_bps": bandwidth_by_stream_type,
        "active_sessions_by_stream_type": active_by_stream_type,
        "active_sessions_by_consumer_prefix": active_by_consumer_prefix,
        "connection_events": connection_events,
        "avg_session_uptime_seconds": avg_uptime,
    })
    
    return stats

@router.get("/health")
async def get_streaming_health() -> Dict[str, Any]:
    """
    Get health status of streaming system
    
    Returns:
        Dict[str, Any]: Health status information
    """
    registry = StreamingSessionRegistry.get_instance()
    active_sessions = registry.get_active_sessions()
    
    # Check for stalled sessions
    stalled_sessions = sum(1 for session in active_sessions if session.is_stalled())
    
    # Check for sessions with connection errors
    error_sessions = sum(1 for session in active_sessions if session.connection_errors > 0)
    sessions_by_stream_type: Dict[str, int] = {}
    stalled_by_stream_type: Dict[str, int] = {}
    error_by_stream_type: Dict[str, int] = {}

    for session in active_sessions:
        sessions_by_stream_type[session.stream_type] = sessions_by_stream_type.get(session.stream_type, 0) + 1
        if session.is_stalled():
            stalled_by_stream_type[session.stream_type] = stalled_by_stream_type.get(session.stream_type, 0) + 1
        if session.connection_errors > 0:
            error_by_stream_type[session.stream_type] = error_by_stream_type.get(session.stream_type, 0) + 1
    
    # Calculate health score (0-100%)
    if active_sessions:
        active_count = len(active_sessions)
        # Ensure we don't divide by zero, although the 'if active_sessions' check should prevent this
        if active_count > 0:
            health_score = 100 - (stalled_sessions / active_count * 50) - (error_sessions / active_count * 30)
            health_score = max(0, min(100, health_score))
        else:
            # Should not be reachable due to outer if, but safe fallback
            health_score = 100 
    else:
        # No active sessions means the system is healthy (or idle)
        health_score = 100
        stalled_sessions = 0
        error_sessions = 0
    
    return {
        "health_score": health_score,
        "stalled_sessions": stalled_sessions,
        "error_sessions": error_sessions,
        "total_active_sessions": len(active_sessions),
        "sessions_by_stream_type": sessions_by_stream_type,
        "stalled_by_stream_type": stalled_by_stream_type,
        "error_by_stream_type": error_by_stream_type,
        "status": "healthy" if health_score > 80 else "degraded" if health_score > 50 else "unhealthy"
    }
