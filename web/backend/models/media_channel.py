from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON
from sqlalchemy.sql import func

from web.backend.database.database import Base


class MediaChannel(Base):
    __tablename__ = "media_channels"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    media_list_id = Column(Integer, ForeignKey("media_lists.id"), nullable=False)
    current_video_id = Column(Integer, nullable=True)
    current_index = Column(Integer, nullable=False, default=0)
    playback_state = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
