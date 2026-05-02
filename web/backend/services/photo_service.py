import mimetypes
import os
import shutil
from typing import BinaryIO, List, Optional

from PIL import Image
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from web.backend.models.photo import PhotoModel
from web.backend.schemas.photo import PhotoCreate, PhotoUpdate


class PhotoService:
    def __init__(self, db: Session):
        self.db = db

    def get_photos(self, skip: int = 0, limit: int = 100, category: Optional[str] = None) -> List[PhotoModel]:
        query = self.db.query(PhotoModel)
        if category:
            query = query.filter(PhotoModel.category == category)
        return query.offset(skip).limit(limit).all()

    def get_photo_by_id(self, photo_id: int) -> Optional[PhotoModel]:
        return self.db.query(PhotoModel).filter(PhotoModel.id == photo_id).first()

    def get_photo_by_path(self, path: str) -> Optional[PhotoModel]:
        return self.db.query(PhotoModel).filter(PhotoModel.path == path).first()

    def create_photo(self, photo: PhotoCreate) -> PhotoModel:
        if not os.path.exists(photo.path):
            raise ValueError(f"Photo file not found: {photo.path}")
        existing = self.get_photo_by_path(photo.path)
        if existing:
            raise ValueError("This photo has already been added to the library")

        file_name = photo.file_name or os.path.basename(photo.path)
        file_size = photo.file_size if photo.file_size is not None else os.path.getsize(photo.path)
        format_name, resolution = self._get_photo_metadata(photo.path)

        db_photo = PhotoModel(
            name=photo.name,
            path=photo.path,
            file_name=file_name,
            file_size=file_size,
            format=photo.format or format_name,
            resolution=photo.resolution or resolution,
            category=photo.category,
            source_type=photo.source_type,
            source_directory_id=photo.source_directory_id,
        )
        self.db.add(db_photo)
        self.db.commit()
        self.db.refresh(db_photo)
        return db_photo

    def update_photo(self, photo_id: int, photo: PhotoUpdate) -> Optional[PhotoModel]:
        db_photo = self.get_photo_by_id(photo_id)
        if not db_photo:
            return None

        update_data = photo.model_dump(exclude_unset=True)
        if "path" in update_data and update_data["path"] != db_photo.path:
            path = update_data["path"]
            if not os.path.exists(path):
                raise ValueError(f"Photo file not found: {path}")
            format_name, resolution = self._get_photo_metadata(path)
            update_data["file_name"] = os.path.basename(path)
            update_data["file_size"] = os.path.getsize(path)
            update_data["format"] = format_name
            update_data["resolution"] = resolution

        for key, value in update_data.items():
            setattr(db_photo, key, value)

        self.db.commit()
        self.db.refresh(db_photo)
        return db_photo

    def delete_photo(self, photo_id: int) -> bool:
        db_photo = self.get_photo_by_id(photo_id)
        if not db_photo:
            return False
        self.db.delete(db_photo)
        self.db.commit()
        return True

    def upload_photo(self, file: BinaryIO, filename: str, upload_dir: str, name: Optional[str] = None) -> Optional[PhotoModel]:
        try:
            if not os.path.isabs(upload_dir):
                backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                upload_dir = os.path.join(backend_dir, upload_dir)
            os.makedirs(upload_dir, exist_ok=True)
            file_path = os.path.join(upload_dir, filename)
            with open(file_path, "wb") as output:
                shutil.copyfileobj(file, output)
            photo_name = name or os.path.splitext(filename)[0]
            return self.create_photo(PhotoCreate(name=photo_name, path=file_path))
        except Exception:
            return None

    def scan_directory(self, directory: str, category: str = "background", source_directory_id: Optional[int] = None) -> List[PhotoModel]:
        if not os.path.exists(directory):
            raise ValueError(f"Directory not found: {directory}")
        if not os.path.isdir(directory):
            raise ValueError(f"Path is not a directory: {directory}")

        photo_extensions = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".svg"}
        photos_added: List[PhotoModel] = []
        for root, _dirs, files in os.walk(directory):
            for file_name in files:
                ext = os.path.splitext(file_name)[1].lower()
                if ext not in photo_extensions:
                    continue
                file_path = os.path.abspath(os.path.join(root, file_name))
                if self.get_photo_by_path(file_path):
                    continue
                try:
                    db_photo = self.create_photo(
                        PhotoCreate(
                            name=os.path.splitext(file_name)[0],
                            path=file_path,
                            category=category,
                            source_type="directory_scan",
                            source_directory_id=source_directory_id,
                        )
                    )
                    photos_added.append(db_photo)
                except SQLAlchemyError:
                    self.db.rollback()
        return photos_added

    def get_media_type(self, path: str) -> str:
        guessed, _ = mimetypes.guess_type(path)
        return guessed or "image/jpeg"

    def _get_photo_metadata(self, path: str) -> tuple[Optional[str], Optional[str]]:
        try:
            with Image.open(path) as image:
                format_name = image.format.lower() if image.format else None
                resolution = f"{image.width}x{image.height}"
                return format_name, resolution
        except Exception:
            return None, None
