import os
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.schemas.media_channel import MediaChannelCreate, MediaChannelResponse, MediaChannelUpdate
from web.backend.schemas.media_directory import MediaDirectoryCreate, MediaDirectoryResponse, MediaDirectoryUpdate
from web.backend.schemas.media_list import MediaListCreate, MediaListResponse, MediaListUpdate
from web.backend.services.media_channel_service import MediaChannelService
from web.backend.services.media_directory_service import MediaDirectoryService
from web.backend.services.media_list_service import MediaListService


router = APIRouter(prefix="/api/media-library", tags=["media-library"])


@router.get("/directories", response_model=List[MediaDirectoryResponse])
def list_media_directories(db: Session = Depends(get_db)):
    return MediaDirectoryService(db).list_directories()


@router.get("/directories/browse")
def browse_media_directories(path: Optional[str] = Query(None, description="Directory path to browse")):
    current_path = os.path.abspath(os.path.expanduser(path)) if path else os.path.expanduser("~")
    if not os.path.isdir(current_path):
        raise HTTPException(status_code=404, detail=f"Directory not found: {current_path}")

    directories = []
    try:
        for entry in sorted(os.listdir(current_path)):
            full_path = os.path.join(current_path, entry)
            if os.path.isdir(full_path):
                directories.append({"name": entry, "path": full_path})
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=f"Permission denied: {current_path}") from exc

    parent_path = os.path.dirname(current_path)
    if parent_path == current_path:
        parent_path = None

    return {
        "current_path": current_path,
        "parent_path": parent_path,
        "directories": directories,
    }


@router.post("/directories", response_model=MediaDirectoryResponse)
def create_media_directory(payload: MediaDirectoryCreate, db: Session = Depends(get_db)):
    return MediaDirectoryService(db).create_directory(payload)


@router.put("/directories/{directory_id}", response_model=MediaDirectoryResponse)
def update_media_directory(directory_id: int, payload: MediaDirectoryUpdate, db: Session = Depends(get_db)):
    result = MediaDirectoryService(db).update_directory(directory_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Directory not found")
    return result


@router.delete("/directories/{directory_id}")
def delete_media_directory(directory_id: int, db: Session = Depends(get_db)):
    deleted = MediaDirectoryService(db).delete_directory(directory_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Directory not found")
    return {"success": True}


@router.post("/directories/{directory_id}/scan")
def scan_media_directory(directory_id: int, db: Session = Depends(get_db)):
    try:
        return MediaDirectoryService(db).scan_directory(directory_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/lists", response_model=List[MediaListResponse])
def list_media_lists(db: Session = Depends(get_db)):
    return MediaListService(db).list_media_lists()


@router.post("/lists", response_model=MediaListResponse)
def create_media_list(payload: MediaListCreate, db: Session = Depends(get_db)):
    return MediaListService(db).create_media_list(payload)


@router.put("/lists/{list_id}", response_model=MediaListResponse)
def update_media_list(list_id: int, payload: MediaListUpdate, db: Session = Depends(get_db)):
    result = MediaListService(db).update_media_list(list_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Media list not found")
    return result


@router.delete("/lists/{list_id}")
def delete_media_list(list_id: int, db: Session = Depends(get_db)):
    deleted = MediaListService(db).delete_media_list(list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media list not found")
    return {"success": True}


@router.get("/channels", response_model=List[MediaChannelResponse])
def list_media_channels(db: Session = Depends(get_db)):
    return MediaChannelService(db).list_channels()


@router.post("/channels", response_model=MediaChannelResponse)
def create_media_channel(payload: MediaChannelCreate, db: Session = Depends(get_db)):
    return MediaChannelService(db).create_channel(payload)


@router.put("/channels/{channel_id}", response_model=MediaChannelResponse)
def update_media_channel(channel_id: int, payload: MediaChannelUpdate, db: Session = Depends(get_db)):
    result = MediaChannelService(db).update_channel(channel_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Media channel not found")
    return result


@router.post("/channels/{channel_id}/advance", response_model=MediaChannelResponse)
def advance_media_channel(channel_id: int, db: Session = Depends(get_db)):
    result = MediaChannelService(db).advance_channel(channel_id)
    if not result:
        raise HTTPException(status_code=404, detail="Media channel not found")
    return result


@router.delete("/channels/{channel_id}")
def delete_media_channel(channel_id: int, db: Session = Depends(get_db)):
    deleted = MediaChannelService(db).delete_channel(channel_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Media channel not found")
    return {"success": True}
