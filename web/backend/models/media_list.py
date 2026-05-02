from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func

from web.backend.database.database import Base


class MediaList(Base):
    __tablename__ = "media_lists"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    category = Column(String, nullable=False, default="background")
    video_ids = Column(JSON, nullable=False, default=list)
    playback_mode = Column(String, nullable=False, default="sequence")
    shuffle = Column(String, nullable=False, default="false")
    loop = Column(String, nullable=False, default="true")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
