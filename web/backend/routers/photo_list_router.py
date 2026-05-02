from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.schemas.photo_list import PhotoListCreate, PhotoListResponse, PhotoListUpdate
from web.backend.services.photo_list_service import PhotoListService


router = APIRouter(prefix="/api/photo-lists", tags=["photo-lists"])


@router.get("/", response_model=List[PhotoListResponse])
def list_photo_lists(db: Session = Depends(get_db)):
    return PhotoListService(db).list_photo_lists()


@router.post("/", response_model=PhotoListResponse)
def create_photo_list(payload: PhotoListCreate, db: Session = Depends(get_db)):
    return PhotoListService(db).create_photo_list(payload)


@router.put("/{list_id}", response_model=PhotoListResponse)
def update_photo_list(list_id: int, payload: PhotoListUpdate, db: Session = Depends(get_db)):
    result = PhotoListService(db).update_photo_list(list_id, payload)
    if not result:
        raise HTTPException(status_code=404, detail="Photo list not found")
    return result


@router.delete("/{list_id}")
def delete_photo_list(list_id: int, db: Session = Depends(get_db)):
    deleted = PhotoListService(db).delete_photo_list(list_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Photo list not found")
    return {"success": True}
