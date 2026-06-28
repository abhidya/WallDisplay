from sqlalchemy import Boolean, Column, DateTime, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from web.backend.database.database import Base


class MediaSource(Base):
    __tablename__ = "media_sources"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=False)
    enabled = Column(Boolean, nullable=False, default=True)
    status = Column(String, nullable=False, default="idle")
    item_count = Column(Integer, nullable=False, default=0)
    last_refresh_at = Column(DateTime(timezone=True), nullable=True)
    last_success_at = Column(DateTime(timezone=True), nullable=True)
    last_error = Column(Text, nullable=True)
    backoff_until = Column(DateTime(timezone=True), nullable=True)
    etag = Column(String, nullable=True)
    last_modified = Column(String, nullable=True)
    config = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "status": self.status,
            "item_count": self.item_count,
            "last_refresh_at": self.last_refresh_at.isoformat() if self.last_refresh_at else None,
            "last_success_at": self.last_success_at.isoformat() if self.last_success_at else None,
            "last_error": self.last_error,
            "backoff_until": self.backoff_until.isoformat() if self.backoff_until else None,
            "config": self.config or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }


class MediaSourceEntry(Base):
    __tablename__ = "media_source_entries"
    __table_args__ = (
        UniqueConstraint("provider", "canonical_url", name="uq_media_source_provider_canonical_url"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    provider = Column(String, nullable=False, index=True)
    canonical_url = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    page_url = Column(String, nullable=False)
    thumbnail_url = Column(String, nullable=True)
    media_url = Column(String, nullable=True)
    category = Column(String, nullable=True)
    tags = Column(JSON, nullable=False, default=list)
    cache_key = Column(String, nullable=False, index=True)
    cache_status = Column(String, nullable=False, default="fresh")
    import_status = Column(String, nullable=False, default="not_imported")
    imported_video_id = Column(Integer, nullable=True)
    http_etag = Column(String, nullable=True)
    http_last_modified = Column(String, nullable=True)
    failure_reason = Column(Text, nullable=True)
    failed_at = Column(DateTime(timezone=True), nullable=True)
    next_retry_at = Column(DateTime(timezone=True), nullable=True)
    discovered_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    last_checked_at = Column(DateTime(timezone=True), nullable=True)

    def to_dict(self):
        return {
            "id": self.id,
            "provider": self.provider,
            "canonical_url": self.canonical_url,
            "title": self.title,
            "page_url": self.page_url,
            "thumbnail_url": self.thumbnail_url,
            "media_url": self.media_url,
            "category": self.category,
            "tags": self.tags or [],
            "cache_key": self.cache_key,
            "cache_status": self.cache_status,
            "import_status": self.import_status,
            "imported_video_id": self.imported_video_id,
            "failure_reason": self.failure_reason,
            "failed_at": self.failed_at.isoformat() if self.failed_at else None,
            "next_retry_at": self.next_retry_at.isoformat() if self.next_retry_at else None,
            "discovered_at": self.discovered_at.isoformat() if self.discovered_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "last_checked_at": self.last_checked_at.isoformat() if self.last_checked_at else None,
        }
