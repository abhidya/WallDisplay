from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Form, Body
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging

from web.backend.database.database import get_db, SessionLocal
from web.backend.models.video import VideoModel
from web.backend.schemas.video import (
    VideoCreate,
    VideoUpdate,
    VideoResponse,
    VideoList,
    VideoUploadResponse,
)
from web.backend.services.video_service import VideoService  # Local get_video_service is defined below
from web.backend.core.streaming_service import StreamingService
from web.backend.core.twisted_streaming import get_instance as get_twisted_streaming

# Add logger
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(
    prefix="/videos",
    tags=["videos"],
    responses={404: {"description": "Not found"}},
)


# Dependency to get the video service
def get_video_service(db: Session = Depends(get_db)) -> VideoService:
    streaming_service = get_twisted_streaming()
    return VideoService(db, streaming_service)


@router.get("/", response_model=VideoList)
def get_videos(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Get all videos
    """
    videos = video_service.get_videos(skip=skip, limit=limit)
    if category:
        videos = [video for video in videos if video.category == category]
    # Convert datetime objects to strings
    formatted_videos = []
    for video in videos:
        video_dict = video.to_dict()
        formatted_videos.append(video_dict)

    return {
        "videos": formatted_videos,
        "total": len(videos),
    }


@router.get("/{video_id}", response_model=VideoResponse)
def get_video(
    video_id: int,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Get a video by ID
    """
    video = video_service.get_video_by_id(video_id)
    if not video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with ID {video_id} not found",
        )
    return video.to_dict()


@router.post("/", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
def create_video(
    video: VideoCreate,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Create a new video
    """
    try:
        db_video = video_service.create_video(video)
        return db_video.to_dict()
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )


@router.put("/{video_id}", response_model=VideoResponse)
def update_video(
    video_id: int,
    video: VideoUpdate,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Update a video
    """
    db_video = video_service.update_video(video_id, video)
    if not db_video:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with ID {video_id} not found",
        )
    return db_video.to_dict()


@router.delete("/{video_id}")
def delete_video(
    video_id: int,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Delete a video
    """
    success = video_service.delete_video(video_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video with ID {video_id} not found",
        )
    return {"success": True, "message": f"Video with ID {video_id} deleted"}


@router.post("/upload", response_model=VideoUploadResponse)
async def upload_video(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    upload_dir: str = Form("uploads"),
    video_service: VideoService = Depends(get_video_service),
):
    """
    Upload a video file
    """
    # Check if the file is a video
    content_type = file.content_type
    if not content_type or not content_type.startswith("video/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"File is not a video. Content type: {content_type}",
        )

    # Get the file extension
    filename = file.filename
    if not filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File has no name",
        )

    # Upload the video
    try:
        video = video_service.upload_video(
            file.file,
            filename,
            upload_dir,
            name,
        )
        
        if not video:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to upload video - check server logs for details",
            )
    except Exception as e:
        logger.error(f"Error uploading video: {str(e)}")
        # Check for specific error types
        error_detail = str(e)
        if "UNIQUE constraint failed" in error_detail:
            error_detail = f"A video with this path already exists: {os.path.join(upload_dir, filename)}"
        elif "Permission denied" in error_detail:
            error_detail = f"Permission denied writing to upload directory: {upload_dir}"
        elif "No space left" in error_detail:
            error_detail = "No space left on device"
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=error_detail,
        )

    return {
        "success": True,
        "message": f"Video {filename} uploaded successfully",
        "video": video.to_dict() if video else None,
    }


@router.get("/{video_id}/file")
def get_video_file(
    video_id: int,
):
    """
    Get video file for direct playback
    """
    db = SessionLocal()
    try:
        video_service = VideoService(db, get_twisted_streaming())
        video = video_service.get_video_by_id(video_id)
        if not video:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Video with ID {video_id} not found",
            )

        video_path = video.path
    finally:
        db.close()

    if not os.path.exists(video_path):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Video file not found at path: {video_path}",
        )

    return FileResponse(video_path, media_type="video/mp4")

@router.post("/{video_id}/stream")
def stream_video(
    video_id: int,
    serve_ip: Optional[str] = None,
    video_service: VideoService = Depends(get_video_service),
):
    """
    Stream a video
    """
    video_url = video_service.stream_video(video_id, serve_ip)
    if not video_url:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to stream video with ID {video_id}",
        )

    return {"success": True, "url": video_url}


@router.post("/scan-directory")
def scan_directory(
    directory: str = Query(None, description="Directory to scan for videos"),
    category: str = Query("background", description="Category to assign to discovered videos"),
    source_directory_id: Optional[int] = Query(None, description="Source directory identifier"),
    body: dict = Body(None, description="Request body for directory parameter"),
    video_service: VideoService = Depends(get_video_service),
):
    """
    Scan a directory for videos and add them to the database
    Accepts directory from either query parameter or JSON body
    """
    # Get directory from query parameter or body
    scan_dir_param = directory
    if scan_dir_param is None and body:
        scan_dir_param = body.get("directory")

    if not scan_dir_param:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory parameter is required (either in query or body)",
        )

    # Check if directory exists (moved to service, but good to have a quick check here too)
    if not os.path.exists(scan_dir_param) or not os.path.isdir(scan_dir_param):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Directory {scan_dir_param} does not exist or is not a directory.",
        )

    try:
        videos_models = video_service.scan_directory(scan_dir_param, category=category, source_directory_id=source_directory_id)
        formatted_videos = [video.to_dict() for video in videos_models]
        return {
            "success": True,
            "message": f"Found {len(formatted_videos)} videos in {scan_dir_param}",
            "videos": formatted_videos,
        }
    except Exception as e:
        logger.error(f"Error scanning directory {scan_dir_param}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan directory: {str(e)}",
        )


@router.post("/scan")
def scan_videos(
    directory: str = Query(None, description="Directory to scan for videos"),
    category: str = Query("background", description="Category to assign to discovered videos"),
    source_directory_id: Optional[int] = Query(None, description="Source directory identifier"),
    body: dict = Body(None, description="Request body for directory parameter"),
    video_service: VideoService = Depends(get_video_service),
):
    """
    Scan a directory for videos and add them to the database
    This is an alias for the scan-directory endpoint for better API compatibility
    Accepts directory from either query parameter or JSON body
    """
    # Get directory from query parameter or body
    scan_dir_param = directory
    if scan_dir_param is None and body:
        scan_dir_param = body.get("directory")

    if not scan_dir_param:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Directory parameter is required (either as query parameter or in JSON body)"
        )

    try:
        videos_models = video_service.scan_directory(scan_dir_param, category=category, source_directory_id=source_directory_id)
        # The service returns a list of VideoModel, router should format it
        formatted_videos = [video.to_dict() for video in videos_models]
        return {
            "success": True,  # Adding success field for consistency
            "message": f"Found {len(formatted_videos)} videos in {scan_dir_param}",
            "videos": formatted_videos
        }
    except Exception as e:
        logger.error(f"Error scanning directory {scan_dir_param} via /scan: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to scan directory: {str(e)}",
        )
