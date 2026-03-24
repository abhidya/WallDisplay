from typing import Optional

from sqlalchemy.orm import Session

from models.media_channel import MediaChannel
from models.media_list import MediaList
from schemas.media_channel import MediaChannelCreate, MediaChannelResponse, MediaChannelUpdate


class MediaChannelService:
    def __init__(self, db: Session):
        self.db = db

    def list_channels(self):
        channels = self.db.query(MediaChannel).order_by(MediaChannel.name.asc()).all()
        return [self._to_response(channel) for channel in channels]

    def create_channel(self, data: MediaChannelCreate) -> MediaChannelResponse:
        channel = MediaChannel(**data.model_dump())
        if channel.current_video_id is None:
            media_list = self.db.query(MediaList).filter(MediaList.id == channel.media_list_id).first()
            if media_list and media_list.video_ids:
                channel.current_video_id = media_list.video_ids[0]
        self.db.add(channel)
        self.db.commit()
        self.db.refresh(channel)
        return self._to_response(channel)

    def update_channel(self, channel_id: int, update: MediaChannelUpdate) -> Optional[MediaChannelResponse]:
        channel = self.db.query(MediaChannel).filter(MediaChannel.id == channel_id).first()
        if not channel:
            return None
        for key, value in update.model_dump(exclude_unset=True).items():
            setattr(channel, key, value)
        self.db.commit()
        self.db.refresh(channel)
        return self._to_response(channel)

    def advance_channel(self, channel_id: int) -> Optional[MediaChannelResponse]:
        channel = self.db.query(MediaChannel).filter(MediaChannel.id == channel_id).first()
        if not channel:
            return None
        media_list = self.db.query(MediaList).filter(MediaList.id == channel.media_list_id).first()
        if media_list and media_list.video_ids:
            channel.current_index = (channel.current_index + 1) % len(media_list.video_ids)
            channel.current_video_id = media_list.video_ids[channel.current_index]
            self.db.commit()
            self.db.refresh(channel)
        return self._to_response(channel)

    def delete_channel(self, channel_id: int) -> bool:
        channel = self.db.query(MediaChannel).filter(MediaChannel.id == channel_id).first()
        if not channel:
            return False
        self.db.delete(channel)
        self.db.commit()
        return True

    def _to_response(self, channel: MediaChannel) -> MediaChannelResponse:
        return MediaChannelResponse(
            id=channel.id,
            name=channel.name,
            media_list_id=channel.media_list_id,
            current_video_id=channel.current_video_id,
            current_index=channel.current_index,
            playback_state=channel.playback_state or {},
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )
