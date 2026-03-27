from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from database.database import Base

class VideoModel(Base):
    """
    Database model for a video
    """
    __tablename__ = "videos"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    path = Column(String, unique=True)
    file_name = Column(String)
    file_size = Column(Integer)
    duration = Column(Float, nullable=True)
    format = Column(String, nullable=True)
    resolution = Column(String, nullable=True)
    category = Column(String, nullable=False, default="background")
    source_type = Column(String, nullable=False, default="upload")
    source_directory_id = Column(Integer, nullable=True)
    preprocessing_status = Column(String, nullable=False, default="pending")
    preprocessing_error = Column(String, nullable=True)
    overlay_optimized = Column(Boolean, default=False, nullable=False)
    has_subtitle = Column(Boolean, default=False, nullable=False)
    subtitle_path = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # Relationships - using string reference to avoid circular imports
    overlay_configs = relationship("OverlayConfig", back_populates="video", cascade="all, delete-orphan")
    
    def to_dict(self):
        """
        Convert the model to a dictionary
        
        Returns:
            dict: Dictionary representation of the model
        """
        return {
            "id": self.id,
            "name": self.name,
            "path": self.path,
            "file_name": self.file_name,
            "file_size": self.file_size,
            "duration": self.duration,
            "format": self.format,
            "resolution": self.resolution,
            "category": self.category,
            "source_type": self.source_type,
            "source_directory_id": self.source_directory_id,
            "preprocessing_status": self.preprocessing_status,
            "preprocessing_error": self.preprocessing_error,
            "overlay_optimized": self.overlay_optimized,
            "has_subtitle": self.has_subtitle,
            "subtitle_path": self.subtitle_path,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }
