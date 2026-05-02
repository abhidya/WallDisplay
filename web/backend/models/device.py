from sqlalchemy import Column, Integer, String, Boolean, DateTime, JSON
from sqlalchemy.sql import func
from web.backend.database.database import Base

class DeviceModel(Base):
    """
    Database model for a device
    """
    __tablename__ = "devices"
    __table_args__ = {'extend_existing': True}
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, index=True)
    type = Column(String, index=True)
    hostname = Column(String)
    action_url = Column(String, nullable=True)
    friendly_name = Column(String)
    manufacturer = Column(String, nullable=True)
    location = Column(String, nullable=True)
    status = Column(String, default="disconnected")
    is_playing = Column(Boolean, default=False)
    current_video = Column(String, nullable=True)
    playback_position = Column(String, nullable=True)
    playback_duration = Column(String, nullable=True)
    playback_progress = Column(Integer, nullable=True)
    config = Column(JSON, nullable=True)
    streaming_url = Column(String, nullable=True)
    streaming_port = Column(Integer, nullable=True)
    user_control_mode = Column(String, default="auto")  # 'auto', 'manual', 'overlay', 'renderer'
    user_control_expires_at = Column(DateTime(timezone=True), nullable=True)
    user_control_reason = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    playback_started_at = Column(DateTime(timezone=True), nullable=True)
    
    def to_dict(self):
        """
        Convert the model to a dictionary
        
        Returns:
            dict: Dictionary representation of the model
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "hostname": self.hostname,
            "action_url": self.action_url,
            "friendly_name": self.friendly_name,
            "manufacturer": self.manufacturer,
            "location": self.location,
            "status": self.status,
            "is_playing": self.is_playing,
            "current_video": self.current_video,
            "playback_position": self.playback_position,
            "playback_duration": self.playback_duration,
            "playback_progress": self.playback_progress,
            "config": self.config,
            "streaming_url": self.streaming_url,
            "streaming_port": self.streaming_port,
            "user_control_mode": self.user_control_mode,
            "user_control_expires_at": self.user_control_expires_at.isoformat() if self.user_control_expires_at else None,
            "user_control_reason": self.user_control_reason,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "playback_started_at": self.playback_started_at.isoformat() if self.playback_started_at else None,
        }
