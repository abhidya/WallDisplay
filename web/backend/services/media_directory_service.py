from typing import List, Optional

from sqlalchemy.orm import Session

from models.media_directory import MediaDirectory
from schemas.media_directory import MediaDirectoryCreate, MediaDirectoryResponse, MediaDirectoryUpdate
from services.video_service import VideoService
from core.twisted_streaming import get_instance as get_twisted_streaming


class MediaDirectoryService:
    def __init__(self, db: Session):
        self.db = db
        self.video_service = VideoService(db, get_twisted_streaming())

    def list_directories(self) -> List[MediaDirectoryResponse]:
        directories = self.db.query(MediaDirectory).order_by(MediaDirectory.name.asc()).all()
        return [self._to_response(item) for item in directories]

    def create_directory(self, data: MediaDirectoryCreate) -> MediaDirectoryResponse:
        directory = MediaDirectory(**data.model_dump())
        self.db.add(directory)
        self.db.commit()
        self.db.refresh(directory)
        return self._to_response(directory)

    def update_directory(self, directory_id: int, update: MediaDirectoryUpdate) -> Optional[MediaDirectoryResponse]:
        directory = self.db.query(MediaDirectory).filter(MediaDirectory.id == directory_id).first()
        if not directory:
            return None
        for key, value in update.model_dump(exclude_unset=True).items():
            setattr(directory, key, value)
        self.db.commit()
        self.db.refresh(directory)
        return self._to_response(directory)

    def delete_directory(self, directory_id: int) -> bool:
        directory = self.db.query(MediaDirectory).filter(MediaDirectory.id == directory_id).first()
        if not directory:
            return False
        self.db.delete(directory)
        self.db.commit()
        return True

    def scan_directory(self, directory_id: int) -> dict:
        directory = self.db.query(MediaDirectory).filter(MediaDirectory.id == directory_id).first()
        if not directory:
            raise ValueError("Directory not found")
        videos = self.video_service.scan_directory(
            directory.path,
            category=directory.category,
            source_directory_id=directory.id,
        )
        return {
            "directory": self._to_response(directory),
            "videos": [video.to_dict() for video in videos],
            "count": len(videos),
        }

    def _to_response(self, directory: MediaDirectory) -> MediaDirectoryResponse:
        return MediaDirectoryResponse(
            id=directory.id,
            name=directory.name,
            path=directory.path,
            category=directory.category,
            enabled=directory.enabled,
            scan_mode=directory.scan_mode,
            created_at=directory.created_at,
            updated_at=directory.updated_at,
        )
