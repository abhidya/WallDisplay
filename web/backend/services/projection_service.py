from sqlalchemy.orm import Session
from typing import List, Optional
import json
import logging

from web.backend.models.projection import ProjectionConfig
from web.backend.schemas.projection import ProjectionConfigCreate, ProjectionConfigUpdate, ProjectionConfigResponse

logger = logging.getLogger(__name__)

class ProjectionService:
    """Service for managing projection configurations"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_config(self, config: ProjectionConfigCreate) -> ProjectionConfigResponse:
        """Create a new projection configuration"""
        try:
            db_config = ProjectionConfig(
                name=config.name,
                mask_data=config.mask_data.model_dump(),
                zones=[zone.model_dump() for zone in config.zones],
                api_configs=config.api_configs.model_dump()
            )
            
            self.db.add(db_config)
            self.db.commit()
            self.db.refresh(db_config)
            
            return self._to_response(db_config)
        except Exception as e:
            logger.error(f"Error creating projection config: {e}")
            self.db.rollback()
            raise
    
    def get_configs(self) -> List[ProjectionConfigResponse]:
        """Get all projection configurations"""
        configs = self.db.query(ProjectionConfig).all()
        return [self._to_response(config) for config in configs]
    
    def get_config_by_id(self, config_id: int) -> Optional[ProjectionConfigResponse]:
        """Get a specific projection configuration"""
        config = self.db.query(ProjectionConfig).filter(ProjectionConfig.id == config_id).first()
        return self._to_response(config) if config else None
    
    def update_config(self, config_id: int, update_data: ProjectionConfigUpdate) -> Optional[ProjectionConfigResponse]:
        """Update a projection configuration"""
        try:
            config = self.db.query(ProjectionConfig).filter(ProjectionConfig.id == config_id).first()
            if not config:
                return None
            
            # Update fields that are provided
            if update_data.name is not None:
                config.name = update_data.name
            
            if update_data.zones is not None:
                config.zones = [zone.model_dump() for zone in update_data.zones]
            
            if update_data.api_configs is not None:
                config.api_configs = update_data.api_configs.model_dump()
            
            self.db.commit()
            self.db.refresh(config)
            
            return self._to_response(config)
        except Exception as e:
            logger.error(f"Error updating projection config: {e}")
            self.db.rollback()
            raise
    
    def delete_config(self, config_id: int) -> bool:
        """Delete a projection configuration"""
        try:
            config = self.db.query(ProjectionConfig).filter(ProjectionConfig.id == config_id).first()
            if not config:
                return False
            
            self.db.delete(config)
            self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Error deleting projection config: {e}")
            self.db.rollback()
            raise
    
    def duplicate_config(self, config_id: int, new_name: str) -> Optional[ProjectionConfigResponse]:
        """Duplicate a projection configuration"""
        try:
            config = self.db.query(ProjectionConfig).filter(ProjectionConfig.id == config_id).first()
            if not config:
                return None
            
            # Create new config with same data but different name
            new_config = ProjectionConfig(
                name=new_name,
                mask_data=config.mask_data,
                zones=config.zones,
                api_configs=config.api_configs
            )
            
            self.db.add(new_config)
            self.db.commit()
            self.db.refresh(new_config)
            
            return self._to_response(new_config)
        except Exception as e:
            logger.error(f"Error duplicating projection config: {e}")
            self.db.rollback()
            raise
    
    def _to_response(self, config: ProjectionConfig) -> ProjectionConfigResponse:
        """Convert database model to response schema"""
        return ProjectionConfigResponse(
            id=config.id,
            name=config.name,
            mask_data=config.mask_data,
            zones=config.zones,
            api_configs=config.api_configs,
            created_at=config.created_at,
            updated_at=config.updated_at
        )