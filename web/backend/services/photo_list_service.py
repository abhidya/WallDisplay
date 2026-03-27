from typing import List, Optional

from sqlalchemy.orm import Session

from models.photo_list import PhotoList
from schemas.photo_list import PhotoListCreate, PhotoListResponse, PhotoListUpdate


class PhotoListService:
    def __init__(self, db: Session):
        self.db = db

    def list_photo_lists(self) -> List[PhotoListResponse]:
        lists = self.db.query(PhotoList).order_by(PhotoList.name.asc()).all()
        return [self._to_response(item) for item in lists]

    def create_photo_list(self, data: PhotoListCreate) -> PhotoListResponse:
        item = PhotoList(
            name=data.name,
            category=data.category,
            photo_ids=data.photo_ids,
            playback_mode=data.playback_mode,
            shuffle=str(data.shuffle).lower(),
            loop=str(data.loop).lower(),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._to_response(item)

    def update_photo_list(self, item_id: int, update: PhotoListUpdate) -> Optional[PhotoListResponse]:
        item = self.db.query(PhotoList).filter(PhotoList.id == item_id).first()
        if not item:
            return None
        data = update.model_dump(exclude_unset=True)
        if "shuffle" in data:
            data["shuffle"] = str(data["shuffle"]).lower()
        if "loop" in data:
            data["loop"] = str(data["loop"]).lower()
        for key, value in data.items():
            setattr(item, key, value)
        self.db.commit()
        self.db.refresh(item)
        return self._to_response(item)

    def delete_photo_list(self, item_id: int) -> bool:
        item = self.db.query(PhotoList).filter(PhotoList.id == item_id).first()
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def _to_response(self, item: PhotoList) -> PhotoListResponse:
        return PhotoListResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            photo_ids=item.photo_ids or [],
            playback_mode=item.playback_mode,
            shuffle=item.shuffle == "true",
            loop=item.loop == "true",
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
