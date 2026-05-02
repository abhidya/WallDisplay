from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func

from web.backend.database.database import Base


class MappingScene(Base):
    __tablename__ = "mapping_scenes"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    canvas_width = Column(Integer, nullable=False, default=1280)
    canvas_height = Column(Integer, nullable=False, default=720)
    mask_mode = Column(String, nullable=False, default="luminance")
    masks = Column(JSON, nullable=False, default=list)
    groups = Column(JSON, nullable=False, default=list)
    render_settings = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
