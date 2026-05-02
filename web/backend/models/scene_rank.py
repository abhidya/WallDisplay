from sqlalchemy import Column, DateTime, Integer, JSON, String
from sqlalchemy.sql import func

from web.backend.database.database import Base


class SceneRank(Base):
    __tablename__ = "scene_ranks"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False, unique=True)
    orientation = Column(String, nullable=False, default="horizontal")
    scene_ids = Column(JSON, nullable=False, default=list)
    gap_px = Column(Integer, nullable=False, default=0)
    rank_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
