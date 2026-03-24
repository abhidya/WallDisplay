from sqlalchemy.orm import Session
from typing import List, Optional
import json
from datetime import datetime

from models.overlay import OverlayConfig
from models.mapping_scene import MappingScene
from models.media_channel import MediaChannel
from models.media_directory import MediaDirectory
from models.media_list import MediaList
from models.video import VideoModel
from schemas.overlay import (
    OverlayConfigCreate,
    OverlayConfigUpdate,
    OverlayConfigResponse,
    OverlayStreamResponse,
    OverlayWindowInitResponse,
)
from core.streaming_service import get_streaming_service

class OverlayService:
    def __init__(self, db: Session):
        self.db = db
        self.streaming_service = get_streaming_service()

    def create_config(self, config_data: OverlayConfigCreate) -> OverlayConfigResponse:
        """Create a new overlay configuration"""
        self._validate_background_source(config_data.background_type, config_data.video_id, config_data.mapping_scene_id)
        
        # Create new config
        new_config = OverlayConfig(
            name=config_data.name,
            background_type=config_data.background_type,
            video_id=config_data.video_id,
            mapping_scene_id=config_data.mapping_scene_id,
            video_transform=config_data.video_transform.dict(),
            widgets=[w.dict() for w in config_data.widgets],
            api_configs=config_data.api_configs.dict()
        )
        
        self.db.add(new_config)
        self.db.commit()
        self.db.refresh(new_config)
        
        return self._to_response(new_config)

    def list_configs(self, video_id: Optional[int] = None) -> List[OverlayConfigResponse]:
        """List overlay configurations, optionally filtered by video ID"""
        query = self.db.query(OverlayConfig)
        
        if video_id:
            query = query.filter(OverlayConfig.video_id == video_id)
        
        configs = query.order_by(OverlayConfig.updated_at.desc()).all()
        return [self._to_response(config) for config in configs]

    def get_config(self, config_id: int) -> Optional[OverlayConfigResponse]:
        """Get a specific overlay configuration"""
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if config:
            return self._to_response(config)
        return None

    def update_config(self, config_id: int, config_update: OverlayConfigUpdate) -> Optional[OverlayConfigResponse]:
        """Update an overlay configuration"""
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            return None
        
        # Update fields if provided
        if config_update.name is not None:
            config.name = config_update.name
        
        if config_update.background_type is not None or config_update.video_id is not None or config_update.mapping_scene_id is not None:
            background_type = config_update.background_type or config.background_type
            video_id = config_update.video_id if config_update.video_id is not None else config.video_id
            mapping_scene_id = config_update.mapping_scene_id if config_update.mapping_scene_id is not None else config.mapping_scene_id
            self._validate_background_source(background_type, video_id, mapping_scene_id)
            config.background_type = background_type
            config.video_id = video_id
            config.mapping_scene_id = mapping_scene_id

        if config_update.video_transform is not None:
            config.video_transform = config_update.video_transform.dict()
        
        if config_update.widgets is not None:
            config.widgets = [w.dict() for w in config_update.widgets]
        
        if config_update.api_configs is not None:
            config.api_configs = config_update.api_configs.dict()
        
        config.updated_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(config)
        
        return self._to_response(config)

    def delete_config(self, config_id: int) -> bool:
        """Delete an overlay configuration"""
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            return False
        
        self.db.delete(config)
        self.db.commit()
        return True

    def duplicate_config(self, config_id: int, new_name: Optional[str] = None) -> Optional[OverlayConfigResponse]:
        """Duplicate an overlay configuration"""
        original = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not original:
            return None
        
        # Create duplicate
        duplicate = OverlayConfig(
            name=new_name or f"{original.name} (Copy)",
            background_type=original.background_type,
            video_id=original.video_id,
            mapping_scene_id=original.mapping_scene_id,
            video_transform=original.video_transform,
            widgets=original.widgets,
            api_configs=original.api_configs
        )
        
        self.db.add(duplicate)
        self.db.commit()
        self.db.refresh(duplicate)
        
        return self._to_response(duplicate)

    def create_stream(self, video_id: Optional[int], config_id: Optional[int] = None) -> OverlayStreamResponse:
        """Create a background payload for overlay projection"""
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first() if config_id else None
        background_type = config.background_type if config else "video"
        resolved_video_id = config.video_id if config and config.video_id is not None else video_id

        if background_type == "mapping":
            if not config or not config.mapping_scene_id:
                raise ValueError("Mapping overlay config missing mapping_scene_id")
            mapping_scene = self._resolve_mapping_scene(config.mapping_scene_id)
            return OverlayStreamResponse(
                background_type="mapping",
                streaming_url=None,
                port=0,
                video_path=None,
                config_id=config_id,
                mapping_scene=mapping_scene,
            )

        video = self.db.query(VideoModel).filter(VideoModel.id == resolved_video_id).first()
        if not video:
            raise ValueError(f"Video with id {resolved_video_id} not found")
        
        # Log video details
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating overlay stream for video: {video.path}, filename: {video.file_name}")
        
        # Start streaming if not already active
        stream_info = self.streaming_service.get_or_create_stream(
            video.path,
            device_name="overlay",
            stream_type="projection_stream",
            consumer_id=f"overlay-config:{config_id or resolved_video_id}",
        )
        logger.info(f"Stream info returned: {stream_info}")
        
        # Get the actual port and URL from the stream info
        port = stream_info.get('port', 9000)
        streaming_url = stream_info.get('url', '')
        
        # If no URL returned, build one (fallback)
        if not streaming_url:
            logger.warning(f"No URL returned from streaming service, using fallback")
            streaming_url = f"http://localhost:{port}/{video.file_name}"
        
        streaming_url = self._normalize_streaming_url(streaming_url)
        
        logger.info(f"Returning streaming URL: {streaming_url}")
        
        return OverlayStreamResponse(
            background_type="video",
            streaming_url=streaming_url,
            port=port,
            video_path=video.path,
            config_id=config_id
        )

    def get_window_init_payload(self, config_id: int) -> OverlayWindowInitResponse:
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            raise ValueError("Configuration not found")

        stream_info = self.create_stream(config.video_id, config_id)
        return OverlayWindowInitResponse(
            config=self._to_response(config),
            background_type=stream_info.background_type,
            streaming_url=stream_info.streaming_url,
            video_path=stream_info.video_path,
            mapping_scene=stream_info.mapping_scene,
        )

    def _to_response(self, config: OverlayConfig) -> OverlayConfigResponse:
        """Convert database model to response schema"""
        return OverlayConfigResponse(
            id=config.id,
            name=config.name,
            background_type=config.background_type,
            video_id=config.video_id,
            mapping_scene_id=config.mapping_scene_id,
            video_transform=config.video_transform,
            widgets=config.widgets,
            api_configs=config.api_configs,
            created_at=config.created_at,
            updated_at=config.updated_at
        )

    def _validate_background_source(self, background_type: str, video_id: Optional[int], mapping_scene_id: Optional[int]) -> None:
        if background_type == "mapping":
            scene = self.db.query(MappingScene).filter(MappingScene.id == mapping_scene_id).first()
            if not scene:
                raise ValueError(f"Mapping scene with id {mapping_scene_id} not found")
            return

        video = self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            raise ValueError(f"Video with id {video_id} not found")

    def _resolve_mapping_scene(self, scene_id: int) -> dict:
        scene = self.db.query(MappingScene).filter(MappingScene.id == scene_id).first()
        if not scene:
            raise ValueError("Mapping scene not found")
        masks = []
        for mask in scene.masks or []:
            masks.append({
                **mask,
                "url": f"/api/mappings/scenes/{scene.id}/masks/{mask['id']}/file",
            })
        groups = []
        for group in scene.groups or []:
            media_urls = self._resolve_group_media_urls(group)
            groups.append({
                **group,
                "media_url": media_urls[0] if media_urls else None,
                "media_urls": media_urls,
            })
        return {
            "id": scene.id,
            "name": scene.name,
            "canvas_width": scene.canvas_width,
            "canvas_height": scene.canvas_height,
            "mask_mode": scene.mask_mode,
            "masks": masks,
            "groups": groups,
            "render_settings": scene.render_settings or {},
        }

    def _resolve_group_media_urls(self, group: dict) -> List[str]:
        if group.get("media_binding_type") == "direct_url" and group.get("direct_url"):
            return [group.get("direct_url")]

        if group.get("media_binding_type") == "media_directory" and (
            group.get("media_directory_ids") or group.get("media_directory_id")
        ):
            directory_ids = group.get("media_directory_ids") or [group["media_directory_id"]]
            valid_directory_ids = self._normalize_directory_ids(directory_ids)
            if not valid_directory_ids:
                return []
            videos = self.db.query(VideoModel).filter(
                VideoModel.source_directory_id.in_(valid_directory_ids)
            ).order_by(VideoModel.source_directory_id.asc(), VideoModel.name.asc()).all()
            seen_video_ids = set()
            urls = []
            for video in videos:
                if video.id in seen_video_ids:
                    continue
                seen_video_ids.add(video.id)
                playback_url = self._resolve_video_playback_url(video.id)
                if playback_url:
                    urls.append(playback_url)
            return urls

        if group.get("media_binding_type") == "media_list" and group.get("media_list_id"):
            media_list = self.db.query(MediaList).filter(MediaList.id == group["media_list_id"]).first()
            if not media_list or not media_list.video_ids:
                return []
            return [
                url for url in
                (self._resolve_video_playback_url(video_id) for video_id in media_list.video_ids)
                if url
            ]

        video_id = group.get("video_id")
        if group.get("media_binding_type") == "media_channel" and group.get("media_channel_id"):
            channel = self.db.query(MediaChannel).filter(MediaChannel.id == group["media_channel_id"]).first()
            if channel:
                video_id = channel.current_video_id

        if not video_id:
            return []
        playback_url = self._resolve_video_playback_url(video_id)
        return [playback_url] if playback_url else []

    def _normalize_directory_ids(self, directory_ids: List[object]) -> List[int]:
        normalized_ids: List[int] = []
        for directory_id in directory_ids:
            if directory_id in (None, ""):
                continue
            try:
                normalized_ids.append(int(directory_id))
            except (TypeError, ValueError):
                continue
        return normalized_ids

    def _resolve_video_playback_url(self, video_id: int) -> Optional[str]:
        video = self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            return None
        return f"/api/videos/{video_id}/file"

    def _resolve_video_stream_url(self, video_id: int, consumer_hint: Optional[str] = None) -> Optional[str]:
        video = self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            return None
        stream_url = self.streaming_service.get_or_create_stream(
            video.path,
            device_name="overlay-mapping",
            stream_type="overlay_mapping_stream",
            consumer_id=f"mapping-scene:{consumer_hint or video_id}",
        ).get("url")
        return self._normalize_streaming_url(stream_url)

    def _normalize_streaming_url(self, streaming_url: Optional[str]) -> Optional[str]:
        if not streaming_url:
            return streaming_url
        if "/uploads/" in streaming_url:
            return streaming_url
        parts = streaming_url.rsplit("/", 1)
        if len(parts) != 2:
            return streaming_url
        return f"{parts[0]}/uploads/{parts[1]}"
