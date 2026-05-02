from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.sql import func

from web.backend.database.database import Base


class MediaDirectory(Base):
    __tablename__ = "media_directories"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    path = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False, default="background")
    enabled = Column(Boolean, nullable=False, default=True)
    scan_mode = Column(String, nullable=False, default="recursive")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
