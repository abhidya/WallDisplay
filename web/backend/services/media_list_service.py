from typing import List, Optional

from sqlalchemy.orm import Session

from models.media_list import MediaList
from schemas.media_list import MediaListCreate, MediaListResponse, MediaListUpdate


class MediaListService:
    def __init__(self, db: Session):
        self.db = db

    def list_media_lists(self) -> List[MediaListResponse]:
        lists = self.db.query(MediaList).order_by(MediaList.name.asc()).all()
        return [self._to_response(item) for item in lists]

    def create_media_list(self, data: MediaListCreate) -> MediaListResponse:
        item = MediaList(
            name=data.name,
            category=data.category,
            video_ids=data.video_ids,
            playback_mode=data.playback_mode,
            shuffle=str(data.shuffle).lower(),
            loop=str(data.loop).lower(),
        )
        self.db.add(item)
        self.db.commit()
        self.db.refresh(item)
        return self._to_response(item)

    def update_media_list(self, item_id: int, update: MediaListUpdate) -> Optional[MediaListResponse]:
        item = self.db.query(MediaList).filter(MediaList.id == item_id).first()
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

    def delete_media_list(self, item_id: int) -> bool:
        item = self.db.query(MediaList).filter(MediaList.id == item_id).first()
        if not item:
            return False
        self.db.delete(item)
        self.db.commit()
        return True

    def _to_response(self, item: MediaList) -> MediaListResponse:
        return MediaListResponse(
            id=item.id,
            name=item.name,
            category=item.category,
            video_ids=item.video_ids or [],
            playback_mode=item.playback_mode,
            shuffle=item.shuffle == "true",
            loop=item.loop == "true",
            created_at=item.created_at,
            updated_at=item.updated_at,
        )
