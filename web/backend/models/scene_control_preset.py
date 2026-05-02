from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from web.backend.database.database import Base


class SceneControlPreset(Base):
    __tablename__ = "scene_control_presets"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    scene_ids = Column(JSON, nullable=False, default=list)
    group_assignments = Column(JSON, nullable=False, default=dict)
    row_edits = Column(JSON, nullable=False, default=dict)
    rank_id = Column(Integer, nullable=True)
    preset_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
