import hashlib
import hmac
import os
import threading
import time
import re
from urllib.parse import urlencode
from urllib.parse import quote

import requests
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional
import json
from datetime import datetime

from models.overlay import OverlayConfig
from models.mapping_scene import MappingScene
from models.media_channel import MediaChannel
from models.media_directory import MediaDirectory
from models.media_list import MediaList
from models.photo import PhotoModel
from models.photo_list import PhotoList
from models.video import VideoModel
from schemas.overlay import (
    OverlayConfigCreate,
    OverlayConfigUpdate,
    OverlayConfigResponse,
    OverlayStreamResponse,
    OverlayWindowInitResponse,
)
from core.streaming_service import get_streaming_service
from services.overlay_playback_sync_service import get_overlay_playback_sync_service

_LIVE_WIDGET_CACHE: Dict[str, Dict[str, Any]] = {}
_LIVE_WIDGET_CACHE_LOCK = threading.RLock()
_IMAGE_URL_RE = re.compile(r"\.(png|jpe?g|gif|webp|bmp|svg)(\?|$)", re.IGNORECASE)

class OverlayService:
    def __init__(self, db: Session):
        self.db = db
        self.streaming_service = get_streaming_service()
        self._global_api_config_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "uploads",
            "env.overlay_global_api_configs.json",
        )

    def get_global_api_configs(self) -> Dict[str, Any]:
        defaults = OverlayConfigCreate(
            name="defaults",
            background_type="video",
            video_id=None,
            mapping_scene_id=None,
            video_transform={"x": 0, "y": 0, "scale": 1.0, "rotation": 0},
            widgets=[],
            api_configs={},
        ).api_configs.model_dump()
        if not os.path.exists(self._global_api_config_path):
            return defaults
        try:
            with open(self._global_api_config_path, "r", encoding="utf-8") as handle:
                stored = json.load(handle) or {}
        except Exception:
            stored = {}
        return {**defaults, **stored}

    def update_global_api_configs(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        merged = {**self.get_global_api_configs(), **(api_configs or {})}
        os.makedirs(os.path.dirname(self._global_api_config_path), exist_ok=True)
        with open(self._global_api_config_path, "w", encoding="utf-8") as handle:
            json.dump(merged, handle, indent=2, sort_keys=True)
        return merged

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
            config=self._to_response(config, include_global_api_configs=True),
            background_type=stream_info.background_type,
            streaming_url=stream_info.streaming_url,
            video_path=stream_info.video_path,
            mapping_scene=stream_info.mapping_scene,
        )

    def get_window_refresh_state(self, config_id: int) -> dict:
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            raise ValueError("Configuration not found")

        revision_parts = [
            f"config:{config.updated_at.isoformat() if config.updated_at else config.created_at.isoformat() if config.created_at else 'none'}"
        ]
        if os.path.exists(self._global_api_config_path):
            revision_parts.append(f"global-api:{datetime.utcfromtimestamp(os.path.getmtime(self._global_api_config_path)).isoformat()}")

        if config.mapping_scene_id:
            scene = self.db.query(MappingScene).filter(MappingScene.id == config.mapping_scene_id).first()
            if scene:
                revision_parts.append(
                    f"scene:{scene.updated_at.isoformat() if scene.updated_at else scene.created_at.isoformat() if scene.created_at else 'none'}"
                )

        if config.video_id:
            video = self.db.query(VideoModel).filter(VideoModel.id == config.video_id).first()
            if video:
                revision_parts.append(
                    f"video:{video.updated_at.isoformat() if video.updated_at else video.created_at.isoformat() if video.created_at else 'none'}"
                )

        return {
            "config_id": config.id,
            "revision": "|".join(revision_parts),
        }

    def get_live_widget_data(self, config_id: int) -> Dict[str, Any]:
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            raise ValueError("Configuration not found")

        widget_types = {
            (widget or {}).get("type", "").lower()
            for widget in (config.widgets or [])
            if (widget or {}).get("visible", True)
        }
        api_configs = self._merged_api_configs(config.api_configs or {})
        api_revision = self._api_config_revision(api_configs)
        data: Dict[str, Any] = {}

        if "spotify" in widget_types:
            data["spotify"] = self._cached_live_widget_value(
                f"spotify:{config_id}:{api_revision}",
                ttl_seconds=8,
                loader=lambda: self._fetch_spotify_now_playing(api_configs),
            )
        if "calendar" in widget_types:
            data["calendar"] = self._cached_live_widget_value(
                f"calendar:{config_id}:{api_revision}",
                ttl_seconds=60,
                loader=lambda: self._fetch_google_calendar_events(api_configs),
            )
        if "weather" in widget_types:
            data["weather"] = self._cached_live_widget_value(
                f"weather:{config_id}:{api_revision}",
                ttl_seconds=300,
                loader=lambda: self._fetch_weather_summary(api_configs),
            )
        if "gmail" in widget_types:
            data["gmail"] = self._cached_live_widget_value(
                f"gmail:{config_id}:{api_revision}",
                ttl_seconds=20,
                loader=lambda: self._fetch_gmail_summary(api_configs),
            )
        if "transit" in widget_types:
            data["transit"] = self._cached_live_widget_value(
                f"transit:{config_id}:{api_revision}",
                ttl_seconds=30,
                loader=lambda: self._fetch_transit_predictions(api_configs),
            )
        if "steam" in widget_types:
            data["steam"] = self._cached_live_widget_value(
                f"steam:{config_id}:{api_revision}",
                ttl_seconds=30,
                loader=lambda: self._fetch_steam_status(api_configs),
            )
        if "climate" in widget_types:
            data["climate"] = self._cached_live_widget_value(
                f"climate:{config_id}:{api_revision}",
                ttl_seconds=20,
                loader=lambda: self._fetch_tuya_climate(api_configs),
            )

        return {
            "config_id": config_id,
            "updated_at": datetime.utcnow().isoformat(),
            "data": data,
        }

    def _to_response(self, config: OverlayConfig, include_global_api_configs: bool = False) -> OverlayConfigResponse:
        """Convert database model to response schema"""
        api_configs = config.api_configs or {}
        if include_global_api_configs:
            api_configs = self._merged_api_configs(api_configs)
        return OverlayConfigResponse(
            id=config.id,
            name=config.name,
            background_type=config.background_type,
            video_id=config.video_id,
            mapping_scene_id=config.mapping_scene_id,
            video_transform=config.video_transform,
            widgets=config.widgets,
            api_configs=api_configs,
            created_at=config.created_at,
            updated_at=config.updated_at
        )

    def _merged_api_configs(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        merged = dict(self.get_global_api_configs())
        for key, value in (api_configs or {}).items():
            if value not in (None, ""):
                merged[key] = value
        return merged

    def _api_config_revision(self, api_configs: Dict[str, Any]) -> str:
        serialized = json.dumps(api_configs or {}, sort_keys=True, separators=(",", ":"))
        return hashlib.sha1(serialized.encode("utf-8")).hexdigest()[:12]

    def _validate_background_source(self, background_type: str, video_id: Optional[int], mapping_scene_id: Optional[int]) -> None:
        if background_type == "mapping":
            scene = self.db.query(MappingScene).filter(MappingScene.id == mapping_scene_id).first()
            if not scene:
                raise ValueError(f"Mapping scene with id {mapping_scene_id} not found")
            return

        video = self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            raise ValueError(f"Video with id {video_id} not found")

    def _cached_live_widget_value(self, cache_key: str, ttl_seconds: int, loader):
        now = time.time()
        with _LIVE_WIDGET_CACHE_LOCK:
            cached = _LIVE_WIDGET_CACHE.get(cache_key)
            if cached and cached.get("expires_at", 0) > now:
                return cached["value"]

        try:
            value = loader()
        except Exception as exc:
            value = {
                "status": "unavailable",
                "error": str(exc),
            }

        with _LIVE_WIDGET_CACHE_LOCK:
            _LIVE_WIDGET_CACHE[cache_key] = {
                "expires_at": now + ttl_seconds,
                "value": value,
            }
        return value

    def _resolve_api_config(self, api_configs: Dict[str, Any], key: str, env_key: str = "") -> str:
        value = self._merged_api_configs(api_configs).get(key)
        if value not in (None, ""):
            return str(value)
        if env_key:
            return os.getenv(env_key, "")
        return ""

    def _widget_state(self, status: str, message: str = "", **extra: Any) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "status": status,
            "message": message,
        }
        payload.update(extra)
        return payload

    def _refresh_oauth_access_token(self, token_url: str, client_id: str, client_secret: str, refresh_token: str) -> str:
        response = requests.post(
            token_url,
            data={
                "grant_type": "refresh_token",
                "refresh_token": refresh_token,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json()
        return payload.get("access_token", "")

    def _fetch_default_city(self) -> str:
        cache_key = "weather-default-city"
        cached = self._cached_live_widget_value(cache_key, ttl_seconds=3600, loader=lambda: {"_city_loader": True})
        if isinstance(cached, dict) and cached.get("city"):
            return str(cached["city"])

        city = "San Francisco"
        try:
            response = requests.get("https://ipinfo.io/json", timeout=5)
            response.raise_for_status()
            city = ((response.json() or {}).get("city") or city).strip() or city
        except Exception:
            pass

        with _LIVE_WIDGET_CACHE_LOCK:
            _LIVE_WIDGET_CACHE[cache_key] = {
                "expires_at": time.time() + 3600,
                "value": {"city": city},
            }
        return city

    def _fetch_weather_summary(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        api_key = self._resolve_api_config(api_configs, "weather_api_key", "WEATHER_API_KEY")
        if not api_key:
            return self._widget_state("unconfigured", "Configure weather API key")

        city = self._fetch_default_city()
        response = requests.get(
            "https://api.openweathermap.org/data/2.5/weather",
            params={
                "q": city,
                "appid": api_key,
                "units": "imperial",
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() or {}
        weather_info = (payload.get("weather") or [{}])[0]
        main = payload.get("main") or {}
        wind = payload.get("wind") or {}
        return self._widget_state(
            "active",
            weather_info.get("description", "Weather available"),
            temperature=main.get("temp"),
            humidity=main.get("humidity"),
            windSpeed=wind.get("speed", 0),
            windDirection=wind.get("deg", 0),
            conditions=weather_info.get("main", ""),
            description=weather_info.get("description", "Weather unavailable"),
            location=payload.get("name") or city,
        )

    def _fetch_transit_predictions(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        stop_id = self._resolve_api_config(api_configs, "transit_stop_id", "TRANSIT_STOP_ID")
        if not stop_id:
            return self._widget_state("unconfigured", "Configure transit stop ID", routes=[])

        response = requests.get(
            f"https://webservices.umoiq.com/api/pub/v1/agencies/sfmta-cis/stopcodes/{quote(stop_id, safe='')}/predictions",
            params={"key": "0be8ebd0284ce712a63f29dcaf7798c4"},
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() or []
        routes = []
        for route_data in payload:
            values = route_data.get("values") or []
            times = sorted(
                [
                    value.get("minutes")
                    for value in values
                    if value.get("minutes") is not None
                ]
            )
            if not times:
                continue
            route = route_data.get("route") or {}
            routes.append(
                {
                    "title": route.get("title") or route.get("id") or "Route",
                    "id": route.get("id") or "",
                    "times": times,
                }
            )

        status = "active" if routes else "idle"
        message = "Live arrivals available" if routes else "No predictions available right now"
        return self._widget_state(status, message, routes=routes, stop_id=stop_id)

    def _spotify_currently_playing(self, access_token: str) -> requests.Response:
        return requests.get(
            "https://api.spotify.com/v1/me/player/currently-playing",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=10,
        )

    def _fetch_spotify_now_playing(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        client_id = self._resolve_api_config(api_configs, "spotify_client_id", "SPOTIFY_CLIENT_ID")
        client_secret = self._resolve_api_config(api_configs, "spotify_client_secret", "SPOTIFY_CLIENT_SECRET")
        refresh_token = self._resolve_api_config(api_configs, "spotify_refresh_token", "SPOTIFY_REFRESH_TOKEN")
        access_token = self._resolve_api_config(api_configs, "spotify_access_token", "SPOTIFY_ACCESS_TOKEN")
        if not access_token and refresh_token and client_id and client_secret:
            access_token = self._refresh_oauth_access_token(
                "https://accounts.spotify.com/api/token",
                client_id,
                client_secret,
                refresh_token,
            )
        if not access_token:
            return self._widget_state("unconfigured", "Configure Spotify credentials")

        response = self._spotify_currently_playing(access_token)
        if (
            response.status_code == 401
            and refresh_token
            and client_id
            and client_secret
        ):
            access_token = self._refresh_oauth_access_token(
                "https://accounts.spotify.com/api/token",
                client_id,
                client_secret,
                refresh_token,
            )
            if not access_token:
                return self._widget_state("unconfigured", "Configure Spotify credentials")
            response = self._spotify_currently_playing(access_token)
        if response.status_code == 204:
            return self._widget_state("idle", "Nothing is playing right now")
        if response.status_code == 403:
            return self._widget_state("unavailable", "Spotify playback state is unavailable for this account")
        if response.status_code == 429:
            return self._widget_state("unavailable", "Spotify rate limit reached")
        response.raise_for_status()
        payload = response.json() or {}
        item = payload.get("item") or {}
        if not item:
            return self._widget_state("idle", "Open Spotify on a device to resume playback")
        artists = item.get("artists") or []
        album_images = ((item.get("album") or {}).get("images") or [])
        duration_ms = item.get("duration_ms") or 0
        progress_ms = payload.get("progress_ms") or 0
        is_playing = bool(payload.get("is_playing"))
        return self._widget_state(
            "active" if is_playing else "paused",
            "Now playing" if is_playing else "Playback paused",
            title=item.get("name") or "Unknown Track",
            artist=", ".join(filter(None, [artist.get("name") for artist in artists])) or "Unknown Artist",
            album_art=album_images[0].get("url") if album_images else "",
            progress=(progress_ms / duration_ms) if duration_ms else 0,
            progress_ms=progress_ms,
            duration_ms=duration_ms,
            is_playing=is_playing,
            album=((item.get("album") or {}).get("name") or ""),
            device_name=((payload.get("device") or {}).get("name") or ""),
        )

    def _fetch_gmail_summary(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        client_id = self._resolve_api_config(api_configs, "gmail_client_id", "GMAIL_CLIENT_ID")
        client_secret = self._resolve_api_config(api_configs, "gmail_client_secret", "GMAIL_CLIENT_SECRET")
        refresh_token = self._resolve_api_config(api_configs, "gmail_refresh_token", "GMAIL_REFRESH_TOKEN")
        access_token = self._resolve_api_config(api_configs, "gmail_access_token", "GMAIL_ACCESS_TOKEN")
        if not access_token and refresh_token and client_id and client_secret:
            access_token = self._refresh_oauth_access_token(
                "https://oauth2.googleapis.com/token",
                client_id,
                client_secret,
                refresh_token,
            )
        if not access_token:
            return self._widget_state("unconfigured", "Configure Gmail credentials", items=[], count=0)

        list_response = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/messages",
            headers={"Authorization": f"Bearer {access_token}"},
            params={"labelIds": "INBOX", "maxResults": 5, "q": "is:unread"},
            timeout=10,
        )
        if list_response.status_code == 401 and refresh_token and client_id and client_secret:
            access_token = self._refresh_oauth_access_token(
                "https://oauth2.googleapis.com/token",
                client_id,
                client_secret,
                refresh_token,
            )
            if not access_token:
                return self._widget_state("unconfigured", "Configure Gmail credentials", items=[], count=0)
            list_response = requests.get(
                "https://gmail.googleapis.com/gmail/v1/users/me/messages",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"labelIds": "INBOX", "maxResults": 5, "q": "is:unread"},
                timeout=10,
            )
        list_response.raise_for_status()
        messages = (list_response.json().get("messages") or [])[:5]
        items = []
        for message in messages:
            message_response = requests.get(
                f"https://gmail.googleapis.com/gmail/v1/users/me/messages/{message['id']}",
                headers={"Authorization": f"Bearer {access_token}"},
                params={"format": "metadata", "metadataHeaders": ["From", "Subject"]},
                timeout=10,
            )
            message_response.raise_for_status()
            payload = message_response.json()
            headers = {
                header.get("name"): header.get("value")
                for header in ((payload.get("payload") or {}).get("headers") or [])
            }
            items.append(
                {
                    "sender": headers.get("From", "Unknown Sender"),
                    "title": headers.get("Subject", payload.get("snippet", "Unread message")),
                }
            )
        status = "active" if items else "idle"
        message = f"{len(items)} unread messages" if items else "No unread messages"
        return self._widget_state(status, message, items=items, count=len(items))

    def _fetch_google_calendar_events(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        api_key = self._resolve_api_config(api_configs, "google_calendar_api_key", "GOOGLE_CALENDAR_API_KEY")
        calendar_id = self._resolve_api_config(api_configs, "google_calendar_id", "GOOGLE_CALENDAR_ID")
        if not api_key or not calendar_id:
            return self._widget_state("unconfigured", "Configure Google Calendar API key and calendar ID", items=[], count=0)

        now_iso = datetime.utcnow().isoformat(timespec="seconds") + "Z"
        response = requests.get(
            f"https://www.googleapis.com/calendar/v3/calendars/{quote(calendar_id, safe='')}/events",
            params={
                "key": api_key,
                "singleEvents": "true",
                "orderBy": "startTime",
                "timeMin": now_iso,
                "maxResults": 5,
            },
            timeout=10,
        )
        response.raise_for_status()
        payload = response.json() or {}
        items = []
        for item in payload.get("items") or []:
            start_info = item.get("start") or {}
            start_value = start_info.get("dateTime") or start_info.get("date") or ""
            items.append(
                {
                    "title": item.get("summary") or "Untitled event",
                    "when": start_value,
                    "location": item.get("location") or "",
                }
            )
        status = "active" if items else "idle"
        message = f"{len(items)} upcoming events" if items else "No upcoming events"
        return self._widget_state(status, message, items=items, count=len(items))

    def _fetch_steam_status(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        api_key = self._resolve_api_config(api_configs, "steam_api_key", "STEAM_API_KEY")
        steam_id = self._resolve_api_config(api_configs, "steam_id", "STEAM_ID")
        if not api_key or not steam_id:
            return self._widget_state("unconfigured", "Configure Steam API credentials")

        response = requests.get(
            "https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v0002/",
            params={"key": api_key, "steamids": steam_id},
            timeout=10,
        )
        response.raise_for_status()
        players = (((response.json() or {}).get("response") or {}).get("players") or [])
        if not players:
            return self._widget_state("idle", "Steam profile is offline or unavailable")
        player = players[0]
        game = player.get("gameextrainfo", "")
        online_state = player.get("personastate", 0)
        status = "active" if game else "idle"
        if game:
            message = f"{player.get('personaname', 'Player')} is playing now"
        elif online_state:
            message = f"{player.get('personaname', 'Player')} is online"
        else:
            message = f"{player.get('personaname', 'Player')} is offline"
        return self._widget_state(
            status,
            message,
            persona_name=player.get("personaname", "Steam"),
            online_state=online_state,
            game=game,
            avatar=player.get("avatarfull", ""),
        )

    def _fetch_tuya_climate(self, api_configs: Dict[str, Any]) -> Dict[str, Any]:
        access_id = self._resolve_api_config(api_configs, "tuya_access_id", "TUYA_ACCESS_ID")
        access_secret = self._resolve_api_config(api_configs, "tuya_access_secret", "TUYA_ACCESS_SECRET")
        device_id = self._resolve_api_config(api_configs, "tuya_device_id", "TUYA_DEVICE_ID")
        base_url = self._resolve_api_config(api_configs, "tuya_api_base_url", "TUYA_API_BASE_URL") or "https://openapi.tuyaus.com"
        if not access_id or not access_secret or not device_id:
            return self._widget_state("unconfigured", "Configure Tuya climate credentials")

        token = self._get_tuya_token(base_url, access_id, access_secret)
        path = f"/v1.0/devices/{device_id}/status"
        url = f"{base_url.rstrip('/')}{path}"
        timestamp = str(int(time.time() * 1000))
        sign_payload = f"{access_id}{token}{timestamp}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path}"
        signature = hmac.new(
            access_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()
        response = requests.get(
            url,
            headers={
                "client_id": access_id,
                "access_token": token,
                "t": timestamp,
                "sign_method": "HMAC-SHA256",
                "sign": signature,
            },
            timeout=10,
        )
        response.raise_for_status()
        result = (response.json() or {}).get("result") or []
        values = {item.get("code"): item.get("value") for item in result}
        temperature = values.get("temp_current") or values.get("va_temperature")
        humidity = values.get("humidity_value") or values.get("va_humidity")
        normalized_temperature = (float(temperature) / 10.0) if temperature is not None else None
        normalized_humidity = (float(humidity) / 10.0) if humidity is not None else None
        status = "active" if normalized_temperature is not None or normalized_humidity is not None else "idle"
        message = "Climate sensor online" if status == "active" else "Climate data unavailable"
        return self._widget_state(
            status,
            message,
            temperature=normalized_temperature,
            humidity=normalized_humidity,
        )

    def _get_tuya_token(self, base_url: str, access_id: str, access_secret: str) -> str:
        cache_key = f"tuya-token:{base_url}:{access_id}"
        cached = self._cached_live_widget_value(cache_key, ttl_seconds=3500, loader=lambda: {"_token_loader": True})
        if isinstance(cached, dict) and cached.get("token"):
            return cached["token"]

        path = "/v1.0/token?grant_type=1"
        timestamp = str(int(time.time() * 1000))
        sign_payload = f"{access_id}{timestamp}GET\n{hashlib.sha256(b'').hexdigest()}\n\n{path}"
        signature = hmac.new(
            access_secret.encode("utf-8"),
            sign_payload.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest().upper()
        response = requests.get(
            f"{base_url.rstrip('/')}{path}",
            headers={
                "client_id": access_id,
                "t": timestamp,
                "sign_method": "HMAC-SHA256",
                "sign": signature,
            },
            timeout=10,
        )
        response.raise_for_status()
        token = ((response.json() or {}).get("result") or {}).get("access_token", "")
        with _LIVE_WIDGET_CACHE_LOCK:
            _LIVE_WIDGET_CACHE[cache_key] = {
                "expires_at": time.time() + 3500,
                "value": {"token": token},
            }
        return token

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
            media_items = self._resolve_group_media_items(group)
            media_urls = [item["url"] for item in media_items if item.get("url")]
            animation_list_payload = self._resolve_animation_list_payload(group.get("animation_list_id"))
            groups.append({
                **group,
                "media_url": media_urls[0] if media_urls else None,
                "media_urls": media_urls,
                "media_items": media_items,
                "animation_list_payload": animation_list_payload,
                "playback_sync_key": self._resolve_group_source_key(group, media_urls),
            })
        playback_sync_snapshot = get_overlay_playback_sync_service().get_scene_snapshot(scene.id, groups)
        source_snapshots = playback_sync_snapshot.get("sources") or {}
        groups = [
            {
                **group,
                "playback_sync": source_snapshots.get(group.get("playback_sync_key")),
            }
            for group in groups
        ]
        return {
            "id": scene.id,
            "name": scene.name,
            "canvas_width": scene.canvas_width,
            "canvas_height": scene.canvas_height,
            "mask_mode": scene.mask_mode,
            "masks": masks,
            "groups": groups,
            "render_settings": scene.render_settings or {},
            "playback_sync": playback_sync_snapshot,
        }

    def _resolve_animation_list_payload(self, animation_list_id: Optional[str]) -> Optional[Dict[str, Any]]:
        if not animation_list_id:
            return None
        backend_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        path = os.path.join(backend_root, "uploads", "projection", "animation_lists.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as handle:
                items = json.load(handle) or []
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(items, list):
            return None
        return next((item for item in items if item.get("id") == animation_list_id), None)

    def _resolve_group_source_key(self, group: dict, media_urls: List[str]) -> str:
        binding_type = str(group.get("media_binding_type") or "").lower()
        if binding_type == "animation" and group.get("animation_id"):
            return f"animation:{group['animation_id']}"
        if binding_type == "animation_list" and group.get("animation_list_id"):
            return f"animation_list:{group['animation_list_id']}"
        if media_urls:
            return f"{binding_type}:{'|'.join(media_urls)}"
        return f"{binding_type}:group:{group.get('id')}"

    def _resolve_group_media_items(self, group: dict) -> List[Dict[str, Any]]:
        if group.get("media_binding_type") == "direct_url" and group.get("direct_url"):
            url = group.get("direct_url")
            return [{
                "url": url,
                "kind": "image" if _IMAGE_URL_RE.search(url or "") else "video",
                "duration_ms": None,
            }]

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
            items = []
            for video in videos:
                if video.id in seen_video_ids:
                    continue
                seen_video_ids.add(video.id)
                item = self._resolve_video_media_item(video.id)
                if item:
                    items.append(item)
            return items

        if group.get("media_binding_type") == "media_list" and group.get("media_list_id"):
            media_list = self.db.query(MediaList).filter(MediaList.id == group["media_list_id"]).first()
            if not media_list or not media_list.video_ids:
                return []
            return [
                item for item in
                (self._resolve_video_media_item(video_id) for video_id in media_list.video_ids)
                if item
            ]

        if group.get("media_binding_type") == "photo_list" and group.get("photo_list_id"):
            photo_list = self.db.query(PhotoList).filter(PhotoList.id == group["photo_list_id"]).first()
            if not photo_list or not photo_list.photo_ids:
                return []
            return [
                item for item in
                (self._resolve_photo_media_item(photo_id) for photo_id in photo_list.photo_ids)
                if item
            ]

        video_id = group.get("video_id")
        photo_id = group.get("photo_id")
        if group.get("media_binding_type") == "media_channel" and group.get("media_channel_id"):
            channel = self.db.query(MediaChannel).filter(MediaChannel.id == group["media_channel_id"]).first()
            if channel:
                video_id = channel.current_video_id

        if group.get("media_binding_type") == "photo":
            if not photo_id:
                return []
            item = self._resolve_photo_media_item(photo_id)
            return [item] if item else []

        if not video_id:
            return []
        item = self._resolve_video_media_item(video_id)
        return [item] if item else []

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

    def _resolve_video_media_item(self, video_id: int) -> Optional[Dict[str, Any]]:
        video = self.db.query(VideoModel).filter(VideoModel.id == video_id).first()
        if not video:
            return None
        return {
            "id": video.id,
            "url": f"/api/videos/{video_id}/file",
            "kind": "video",
            "duration_ms": int((video.duration or 0) * 1000) if video.duration else None,
            "name": video.name,
        }

    def _resolve_photo_playback_url(self, photo_id: int) -> Optional[str]:
        photo = self.db.query(PhotoModel).filter(PhotoModel.id == photo_id).first()
        if not photo:
            return None
        return f"/api/photos/{photo_id}/file"

    def _resolve_photo_media_item(self, photo_id: int) -> Optional[Dict[str, Any]]:
        photo = self.db.query(PhotoModel).filter(PhotoModel.id == photo_id).first()
        if not photo:
            return None
        return {
            "id": photo.id,
            "url": f"/api/photos/{photo_id}/file",
            "kind": "image",
            "duration_ms": None,
            "name": photo.name,
        }

    def get_mapping_playback_sync(self, config_id: int) -> Dict[str, Any]:
        config = self.db.query(OverlayConfig).filter(OverlayConfig.id == config_id).first()
        if not config:
            raise ValueError("Configuration not found")
        if config.background_type != "mapping" or not config.mapping_scene_id:
            return {
                "config_id": config_id,
                "background_type": config.background_type,
                "server_now_ms": int(time.time() * 1000),
                "sources": {},
            }
        scene = self._resolve_mapping_scene(config.mapping_scene_id)
        snapshot = scene.get("playback_sync") or {}
        snapshot["config_id"] = config_id
        snapshot["background_type"] = config.background_type
        return snapshot

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
