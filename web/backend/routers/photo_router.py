import os
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from web.backend.database.database import SessionLocal, get_db
from web.backend.schemas.photo import PhotoCreate, PhotoListResponseEnvelope, PhotoResponse, PhotoUploadResponse, PhotoUpdate
from web.backend.services.photo_service import PhotoService


router = APIRouter(prefix="/photos", tags=["photos"], responses={404: {"description": "Not found"}})


def get_photo_service(db: Session = Depends(get_db)) -> PhotoService:
    return PhotoService(db)


@router.get("/", response_model=PhotoListResponseEnvelope)
def get_photos(
    skip: int = 0,
    limit: int = 100,
    category: Optional[str] = None,
    photo_service: PhotoService = Depends(get_photo_service),
):
    photos = photo_service.get_photos(skip=skip, limit=limit, category=category)
    return {"photos": [photo.to_dict() for photo in photos], "total": len(photos)}


@router.get("/{photo_id}", response_model=PhotoResponse)
def get_photo(photo_id: int, photo_service: PhotoService = Depends(get_photo_service)):
    photo = photo_service.get_photo_by_id(photo_id)
    if not photo:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo with ID {photo_id} not found")
    return photo.to_dict()


@router.post("/", response_model=PhotoResponse, status_code=status.HTTP_201_CREATED)
def create_photo(photo: PhotoCreate, photo_service: PhotoService = Depends(get_photo_service)):
    try:
        return photo_service.create_photo(photo).to_dict()
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.put("/{photo_id}", response_model=PhotoResponse)
def update_photo(photo_id: int, photo: PhotoUpdate, photo_service: PhotoService = Depends(get_photo_service)):
    try:
        updated = photo_service.update_photo(photo_id, photo)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo with ID {photo_id} not found")
    return updated.to_dict()


@router.delete("/{photo_id}")
def delete_photo(photo_id: int, photo_service: PhotoService = Depends(get_photo_service)):
    if not photo_service.delete_photo(photo_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo with ID {photo_id} not found")
    return {"success": True, "message": f"Photo with ID {photo_id} deleted"}


@router.post("/upload", response_model=PhotoUploadResponse)
async def upload_photo(
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    upload_dir: str = Form("uploads/photos"),
    photo_service: PhotoService = Depends(get_photo_service),
):
    filename = file.filename
    if not filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File has no name")
    photo = photo_service.upload_photo(file.file, filename, upload_dir, name)
    if not photo:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to upload photo")
    return {"success": True, "message": f"Photo {filename} uploaded successfully", "photo": photo.to_dict()}


@router.get("/{photo_id}/file")
def get_photo_file(photo_id: int):
    db = SessionLocal()
    try:
        photo_service = PhotoService(db)
        photo = photo_service.get_photo_by_id(photo_id)
        if not photo:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo with ID {photo_id} not found")
        photo_path = photo.path
        media_type = photo_service.get_media_type(photo_path)
    finally:
        db.close()

    if not os.path.exists(photo_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Photo file not found at path: {photo_path}")
    return FileResponse(photo_path, media_type=media_type)


@router.post("/scan-directory")
def scan_directory(
    directory: str = Query(..., description="Directory to scan for photos"),
    category: str = Query("background", description="Category to assign to discovered photos"),
    source_directory_id: Optional[int] = Query(None, description="Source directory identifier"),
    photo_service: PhotoService = Depends(get_photo_service),
):
    try:
        photos = photo_service.scan_directory(directory, category=category, source_directory_id=source_directory_id)
        return {"photos": [photo.to_dict() for photo in photos], "count": len(photos)}
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
