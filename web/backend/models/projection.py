from sqlalchemy import Column, Integer, String, DateTime, JSON
from sqlalchemy.sql import func
from web.backend.database.database import Base

class ProjectionConfig(Base):
    """
    Database model for projection animation configurations
    """
    __tablename__ = "projection_configs"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    mask_data = Column(JSON, nullable=False)  # Stores mask info including ID, dimensions, zones
    zones = Column(JSON, nullable=False)      # Array of zones with bounds, transforms, and assignments
    api_configs = Column(JSON, nullable=False)  # Weather API key, transit settings, etc.
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    def to_dict(self):
        """Convert model to dictionary"""
        return {
            "id": self.id,
            "name": self.name,
            "mask_data": self.mask_data,
            "zones": self.zones,
            "api_configs": self.api_configs,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None
        }