from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.sql import func

from web.backend.database.database import Base


class PhotoModel(Base):
    __tablename__ = "photos"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    path = Column(String, unique=True)
    file_name = Column(String)
    file_size = Column(Integer)
    format = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
    category = Column(String, nullable=False, default="background")
    source_type = Column(String, nullable=False, default="upload")
    source_directory_id = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "format": self.format,
            "resolution": self.resolution,
            "category": self.category,
            "source_type": self.source_type,
            "source_directory_id": self.source_directory_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
