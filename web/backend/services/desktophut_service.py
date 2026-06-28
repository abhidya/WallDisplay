"""DesktopHut helpers plus the cached media-source adapter."""

from __future__ import annotations

import hashlib
import os
import re
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin, urlparse, urlunparse
from xml.etree import ElementTree

import requests
from bs4 import BeautifulSoup
from sqlalchemy import or_
from sqlalchemy.orm import Session

from web.backend.core.twisted_streaming import get_instance as get_twisted_streaming
from web.backend.database.database import ensure_sqlite_schema_compatibility
from web.backend.models.media_source import MediaSource, MediaSourceEntry
from web.backend.schemas.video import VideoCreate
from web.backend.services.video_service import VideoService

BASE_URL = "https://www.desktophut.com"
SEARCH_URL = f"{BASE_URL}/search"
SITEMAP_URL = f"{BASE_URL}/sitemap.xml"
ROBOTS_URL = f"{BASE_URL}/robots.txt"
PROVIDER = "desktophut"
DEFAULT_EXCLUDE_TAG = "Girl"
DEFAULT_USER_AGENT = "WallDisplay DesktopHut media-source/1.0 (+https://github.com/abhidya/WallDisplay)"
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm"}
BACKOFF_STATUSES = {403, 429, 500, 502, 503, 504}

CATEGORIES: Dict[str, str] = {
    "25": "3D Animation", "15": "Abstract", "16": "Animals", "12": "Animated Wallpapers",
    "14": "Anime", "80": "Black", "45": "Black and White", "22": "Car", "23": "Comics",
    "28": "Free Live Wallpapers", "24": "Free Stock Video Footage", "18": "Games",
    "29": "Holidays", "19": "Landscape", "43": "Lofi", "41": "Manga", "13": "Mobile",
    "20": "Movie_Tv", "30": "Movies_and_TV", "27": "Nature", "46": "Other",
    "31": "People", "21": "Pixel", "36": "Preppy", "35": "Sci_fi_Fantasy_Live",
    "17": "Sci-fi", "34": "Sci-fi_Fantasy", "40": "Screensavers", "11": "Software_Page",
    "79": "Space", "26": "Tech", "33": "Vehicles", "37": "Wallpaper_Engine",
    "32": "World", "42": "Remastered_4K",
}


@dataclass(frozen=True)
class DesktopHutVideo:
    id: str
    title: str
    preview_url: str
    category_id: Optional[str] = None
    category_name: Optional[str] = None
    page: int = 1
    alt_text: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "preview_url": self.preview_url,
            "category_id": self.category_id,
            "category_name": self.category_name,
            "page": self.page,
            "alt_text": self.alt_text,
        }


def utcnow() -> datetime:
    return datetime.utcnow()


def sanitize_filename(filename: str, fallback: str = "unnamed", max_length: int = 120) -> str:
    clean = re.sub(r"[^\w\s.-]", "", str(filename or "")).strip().replace(" ", "_")
    clean = re.sub(r"_+", "_", clean).strip("._-")
    return (clean or fallback)[:max_length]


def normalize_category(category: Optional[str]) -> tuple[Optional[str], Optional[str]]:
    if category is None or str(category).strip() == "":
        return None, None
    value = str(category).strip()
    if value in CATEGORIES:
        return value, CATEGORIES[value]
    lowered = value.lower().replace("_", " ").replace("-", " ")
    for cat_id, cat_name in CATEGORIES.items():
        candidate = cat_name.lower().replace("_", " ").replace("-", " ")
        if lowered == candidate:
            return cat_id, cat_name
    raise ValueError(f"Unknown DesktopHut category: {category}")


def category_folder_name(category_name: Optional[str], fallback: str = "DesktopHut") -> str:
    return sanitize_filename((category_name or fallback).replace(" ", "_"), fallback=fallback)


def _canonical_url(url: str) -> str:
    parsed = urlparse(urljoin(BASE_URL, url))
    return urlunparse((parsed.scheme, parsed.netloc.lower(), parsed.path.rstrip("/") or "/", "", "", ""))


def _cache_key(url: str) -> str:
    return hashlib.sha256(_canonical_url(url).encode("utf-8")).hexdigest()


class DesktopHutService:
    def __init__(
        self,
        db: Optional[Session] = None,
        session: Optional[requests.Session] = None,
        timeout: int = 20,
        request_delay_seconds: float = 1.0,
    ):
        self.db = db
        self.session = session or requests.Session()
        self.timeout = timeout
        self.request_delay_seconds = request_delay_seconds
        self._last_request_at = 0.0
        self._robots_rules: Optional[List[str]] = None

    def list_categories(self) -> List[Dict[str, str]]:
        return [{"id": cat_id, "name": name} for cat_id, name in CATEGORIES.items()]

    def list_sources(self) -> List[Dict[str, Any]]:
        return [self._source().to_dict()]

    def get_status(self) -> Dict[str, Any]:
        source = self._source()
        source.item_count = self._entry_query().count()
        self.db.commit()
        return source.to_dict()

    def refresh_cache(self, max_pages: int = 25, force: bool = False) -> Dict[str, Any]:
        source = self._source()
        now = utcnow()
        if source.backoff_until and source.backoff_until > now and not force:
            return {"success": False, "status": "backoff", "source": source.to_dict(), "items_seen": 0, "items_updated": 0}
        if source.status == "refreshing" and not force:
            return {"success": False, "status": "refreshing", "source": source.to_dict(), "items_seen": 0, "items_updated": 0}

        source.status = "refreshing"
        source.last_refresh_at = now
        source.last_error = None
        self.db.commit()

        seen = 0
        updated = 0
        try:
            if not self._robots_allowed(SITEMAP_URL):
                raise PermissionError("robots.txt disallows sitemap crawl")
            sitemap_text, sitemap_headers, sitemap_status = self._fetch_text(
                SITEMAP_URL,
                etag=None if force else source.etag,
                last_modified=None if force else source.last_modified,
            )
            if sitemap_status == 304:
                source.status = "idle"
                source.last_success_at = utcnow()
                self.db.commit()
                return {"success": True, "status": "not_modified", "source": source.to_dict(), "items_seen": 0, "items_updated": 0}

            source.etag = sitemap_headers.get("ETag") or sitemap_headers.get("etag") or source.etag
            source.last_modified = sitemap_headers.get("Last-Modified") or sitemap_headers.get("last-modified") or source.last_modified
            urls = self._collect_sitemap_page_urls(sitemap_text)
            for page_url in urls[: max(1, int(max_pages or 1))]:
                seen += 1
                entry = self._upsert_page_from_url(page_url, force=force)
                if entry:
                    updated += 1
            source.item_count = self._entry_query().count()
            source.status = "idle"
            source.last_success_at = utcnow()
            self.db.commit()
            return {"success": True, "status": "refreshed", "source": source.to_dict(), "items_seen": seen, "items_updated": updated}
        except Exception as exc:  # noqa: BLE001 - API must report unavailable provider without crashing.
            self.db.rollback()
            source = self._source()
            source.status = "error"
            source.last_error = str(exc)
            source.last_refresh_at = now
            if isinstance(exc, PermissionError):
                source.backoff_until = utcnow() + timedelta(hours=1)
            self.db.commit()
            return {"success": False, "status": "error", "error": str(exc), "source": source.to_dict(), "items_seen": seen, "items_updated": updated}

    def browse_entries(self, query: str = "", offset: int = 0, limit: int = 50) -> Dict[str, Any]:
        db_query = self._entry_query()
        clean_query = str(query or "").strip()
        if clean_query:
            pattern = f"%{clean_query}%"
            db_query = db_query.filter(or_(MediaSourceEntry.title.ilike(pattern), MediaSourceEntry.category.ilike(pattern)))
        total = db_query.count()
        entries = db_query.order_by(MediaSourceEntry.discovered_at.desc()).offset(max(0, offset)).limit(max(1, min(limit, 100))).all()
        return {"entries": [entry.to_dict() for entry in entries], "total": total}

    def import_entry(self, entry_id: int, upload_dir: Optional[str] = None) -> Dict[str, Any]:
        entry = self._entry_query().filter(MediaSourceEntry.id == entry_id).first()
        if not entry:
            raise ValueError("DesktopHut entry not found")
        if entry.imported_video_id:
            return {"success": True, "duplicate": True, "entry": entry.to_dict(), "video_id": entry.imported_video_id}
        if not entry.media_url:
            raise ValueError("DesktopHut entry has no public media URL to import")
        if not self._robots_allowed(entry.media_url):
            raise PermissionError("robots.txt disallows media import URL")

        upload_root = Path(upload_dir or Path(__file__).resolve().parent.parent / "uploads" / "desktophut")
        upload_root.mkdir(parents=True, exist_ok=True)
        ext = Path(urlparse(entry.media_url).path).suffix.lower()
        if ext not in VIDEO_EXTENSIONS:
            ext = ".mp4"
        destination = upload_root / f"{sanitize_filename(entry.title, fallback=str(entry.id))}{ext}"
        suffix = 1
        while destination.exists():
            existing = VideoService(self.db, get_twisted_streaming()).get_video_by_path(str(destination))
            if existing:
                entry.import_status = "imported"
                entry.imported_video_id = existing.id
                self.db.commit()
                return {"success": True, "duplicate": True, "entry": entry.to_dict(), "video_id": existing.id}
            destination = upload_root / f"{sanitize_filename(entry.title, fallback=str(entry.id))}_{suffix}{ext}"
            suffix += 1

        self._download_public_media(entry.media_url, destination)
        video = VideoService(self.db, get_twisted_streaming()).create_video(VideoCreate(
            name=entry.title,
            path=str(destination),
            source_type=PROVIDER,
            category=entry.category or "background",
        ))
        entry.import_status = "imported"
        entry.imported_video_id = video.id
        self.db.commit()
        self.db.refresh(entry)
        return {"success": True, "duplicate": False, "entry": entry.to_dict(), "video": video.to_dict()}

    def preview_category(
        self,
        category: str,
        page: int = 1,
        limit: int = 20,
        exclude_tag: str = DEFAULT_EXCLUDE_TAG,
    ) -> List[Dict[str, Any]]:
        cat_id, cat_name = normalize_category(category)
        return [item.to_dict() for item in self._fetch_page(
            category_id=cat_id,
            category_name=cat_name,
            page=page,
            limit=limit,
            exclude_tag=exclude_tag,
        )]

    def search_videos(
        self,
        query: str,
        category: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        exclude_tag: str = DEFAULT_EXCLUDE_TAG,
    ) -> List[Dict[str, Any]]:
        if not str(query or "").strip():
            raise ValueError("query is required")
        cat_id, cat_name = normalize_category(category)
        return [item.to_dict() for item in self._fetch_page(
            query=str(query).strip(),
            category_id=cat_id,
            category_name=cat_name,
            page=page,
            limit=limit,
            exclude_tag=exclude_tag,
        )]

    def download_category(self, category: str, output_root: str, max_videos: int = 10, page_start: int = 1, max_pages: int = 3, exclude_tag: str = DEFAULT_EXCLUDE_TAG, overwrite: bool = False) -> Dict[str, Any]:
        cat_id, cat_name = normalize_category(category)
        folder = self._prepare_output_dir(output_root, category_folder_name(cat_name))
        candidates = self._collect_candidates(category_id=cat_id, category_name=cat_name, page_start=page_start, max_pages=max_pages, max_videos=max_videos, exclude_tag=exclude_tag)
        return self._download_candidates(candidates, folder, max_videos=max_videos, overwrite=overwrite)

    def download_search(self, query: str, output_root: str, category: Optional[str] = None, folder_name: Optional[str] = None, max_videos: int = 10, page_start: int = 1, max_pages: int = 3, exclude_tag: str = DEFAULT_EXCLUDE_TAG, overwrite: bool = False) -> Dict[str, Any]:
        if not str(query or "").strip():
            raise ValueError("query is required")
        cat_id, cat_name = normalize_category(category)
        folder = self._prepare_output_dir(output_root, folder_name or sanitize_filename(query, fallback="search"))
        candidates = self._collect_candidates(query=str(query).strip(), category_id=cat_id, category_name=cat_name, page_start=page_start, max_pages=max_pages, max_videos=max_videos, exclude_tag=exclude_tag)
        return self._download_candidates(candidates, folder, max_videos=max_videos, overwrite=overwrite)

    def _source(self) -> MediaSource:
        if self.db is None:
            raise ValueError("database session is required")
        source = self.db.query(MediaSource).filter(MediaSource.provider == PROVIDER).first()
        if source:
            return source
        source = MediaSource(
            provider=PROVIDER,
            display_name="DesktopHut",
            enabled=True,
            status="idle",
            config={
                "sitemap_url": SITEMAP_URL,
                "robots_url": ROBOTS_URL,
                "request_delay_seconds": self.request_delay_seconds,
                "user_agent": DEFAULT_USER_AGENT,
            },
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def _entry_query(self):
        if self.db is None:
            raise ValueError("database session is required")
        return self.db.query(MediaSourceEntry).filter(MediaSourceEntry.provider == PROVIDER)

    def _request_headers(self, etag: Optional[str] = None, last_modified: Optional[str] = None) -> Dict[str, str]:
        headers = {"User-Agent": DEFAULT_USER_AGENT, "Accept": "text/html,application/xml;q=0.9,*/*;q=0.8"}
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified
        return headers

    def _polite_get(self, url: str, **kwargs: Any):
        elapsed = time.monotonic() - self._last_request_at
        if elapsed < self.request_delay_seconds:
            time.sleep(self.request_delay_seconds - elapsed)
        response = self.session.get(url, timeout=self.timeout, **kwargs)
        self._last_request_at = time.monotonic()
        return response

    def _fetch_text(self, url: str, etag: Optional[str] = None, last_modified: Optional[str] = None) -> tuple[str, Dict[str, str], int]:
        response = self._polite_get(url, headers=self._request_headers(etag, last_modified))
        status = int(getattr(response, "status_code", 200) or 200)
        headers = dict(getattr(response, "headers", {}) or {})
        if status in BACKOFF_STATUSES:
            self._set_source_backoff(status)
        if status == 304:
            return "", headers, status
        response.raise_for_status()
        return getattr(response, "text", "") or "", headers, status

    def _set_source_backoff(self, status: int):
        if self.db is None:
            return
        source = self._source()
        minutes = 60 if status in {403, 429} else 15
        source.backoff_until = utcnow() + timedelta(minutes=minutes)
        source.last_error = f"DesktopHut returned HTTP {status}; backing off"
        self.db.commit()

    def _robots_allowed(self, target_url: str) -> bool:
        if self._robots_rules is None:
            try:
                response = self._polite_get(ROBOTS_URL, headers=self._request_headers())
                status = int(getattr(response, "status_code", 200) or 200)
                if status in BACKOFF_STATUSES:
                    self._set_source_backoff(status)
                    return False
                text = getattr(response, "text", "") or ""
                self._robots_rules = self._parse_robots_disallow(text)
            except Exception:
                self._robots_rules = ["/"]
        path = urlparse(target_url).path or "/"
        return not any(path.startswith(rule) for rule in (self._robots_rules or []))

    def _parse_robots_disallow(self, text: str) -> List[str]:
        active = False
        rules: List[str] = []
        for raw_line in text.splitlines():
            line = raw_line.split("#", 1)[0].strip()
            if not line or ":" not in line:
                continue
            key, value = [part.strip() for part in line.split(":", 1)]
            key = key.lower()
            if key == "user-agent":
                active = value == "*"
            elif active and key == "disallow" and value:
                rules.append(value)
            elif key == "user-agent" and active:
                active = False
        return rules

    def _parse_sitemap_urls(self, text: str) -> List[str]:
        root = ElementTree.fromstring(text)
        urls: List[str] = []
        for element in root.iter():
            if element.tag.endswith("loc") and element.text:
                candidate = _canonical_url(element.text.strip())
                parsed = urlparse(candidate)
                if parsed.netloc == "www.desktophut.com" and parsed.path not in {"", "/"}:
                    urls.append(candidate)
        return list(dict.fromkeys(urls))

    def _collect_sitemap_page_urls(self, sitemap_text: str, max_sitemaps: int = 10) -> List[str]:
        page_urls: List[str] = []
        nested_sitemaps = 0
        for candidate in self._parse_sitemap_urls(sitemap_text):
            if urlparse(candidate).path.lower().endswith(".xml"):
                if nested_sitemaps >= max_sitemaps or not self._robots_allowed(candidate):
                    continue
                nested_sitemaps += 1
                nested_text, _headers, status = self._fetch_text(candidate)
                if status != 304:
                    page_urls.extend(self._parse_sitemap_urls(nested_text))
            else:
                page_urls.append(candidate)
        return list(dict.fromkeys(page_urls))

    def _upsert_page_from_url(self, page_url: str, force: bool = False) -> Optional[MediaSourceEntry]:
        canonical = _canonical_url(page_url)
        entry = self._entry_query().filter(MediaSourceEntry.canonical_url == canonical).first()
        now = utcnow()
        if entry and entry.next_retry_at and entry.next_retry_at > now and not force:
            return None
        if entry and entry.last_checked_at and entry.cache_status == "fresh" and not force:
            return entry
        if not self._robots_allowed(canonical):
            return self._mark_entry_failure(entry, canonical, "robots.txt disallows page crawl")
        try:
            html, headers, status = self._fetch_text(
                canonical,
                etag=entry.http_etag if entry else None,
                last_modified=entry.http_last_modified if entry else None,
            )
            if status == 304 and entry:
                entry.last_checked_at = now
                return entry
            metadata = self.extract_metadata(html, canonical)
            if entry is None:
                entry = MediaSourceEntry(provider=PROVIDER, canonical_url=canonical, page_url=canonical, cache_key=_cache_key(canonical), title=metadata["title"])
                self.db.add(entry)
            entry.title = metadata["title"]
            entry.page_url = canonical
            entry.thumbnail_url = metadata.get("thumbnail_url")
            entry.media_url = metadata.get("media_url")
            entry.category = metadata.get("category")
            entry.tags = metadata.get("tags") or []
            entry.cache_status = "fresh"
            entry.failure_reason = None
            entry.failed_at = None
            entry.next_retry_at = None
            entry.last_checked_at = now
            entry.http_etag = headers.get("ETag") or headers.get("etag") or entry.http_etag
            entry.http_last_modified = headers.get("Last-Modified") or headers.get("last-modified") or entry.http_last_modified
            self.db.commit()
            self.db.refresh(entry)
            return entry
        except Exception as exc:  # noqa: BLE001 - cache bad pages to avoid hammering.
            return self._mark_entry_failure(entry, canonical, str(exc))

    def _mark_entry_failure(self, entry: Optional[MediaSourceEntry], canonical: str, reason: str) -> MediaSourceEntry:
        if entry is None:
            entry = MediaSourceEntry(provider=PROVIDER, canonical_url=canonical, page_url=canonical, cache_key=_cache_key(canonical), title="DesktopHut entry")
            self.db.add(entry)
        entry.cache_status = "failed"
        entry.failure_reason = reason
        entry.failed_at = utcnow()
        entry.next_retry_at = utcnow() + timedelta(hours=6)
        entry.last_checked_at = utcnow()
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def extract_metadata(self, html: str, page_url: str) -> Dict[str, Any]:
        soup = BeautifulSoup(html or "", "html.parser")
        title = self._meta_content(soup, "og:title") or self._text_of(soup, "h1") or self._text_of(soup, "title") or "DesktopHut wallpaper"
        thumbnail = self._meta_content(soup, "og:image") or self._first_attr(soup, "img", "src")
        media = (
            self._meta_content(soup, "og:video")
            or self._meta_content(soup, "og:video:url")
            or self._first_attr(soup, "video source", "src")
            or self._first_attr(soup, "video", "src")
        )
        tags = [item.get("content", "").strip() for item in soup.select('meta[property="article:tag"], meta[name="keywords"]') if item.get("content")]
        category = self._text_of(soup, ".breadcrumb a:last-child") or None
        return {
            "title": re.sub(r"\s+", " ", title).strip(),
            "thumbnail_url": urljoin(page_url, thumbnail) if thumbnail else None,
            "media_url": urljoin(page_url, media) if media else None,
            "category": category,
            "tags": tags,
        }

    def _meta_content(self, soup: BeautifulSoup, key: str) -> Optional[str]:
        element = soup.find("meta", property=key) or soup.find("meta", attrs={"name": key})
        return str(element.get("content")).strip() if element and element.get("content") else None

    def _text_of(self, soup: BeautifulSoup, selector: str) -> Optional[str]:
        element = soup.select_one(selector)
        return element.get_text(" ", strip=True) if element else None

    def _first_attr(self, soup: BeautifulSoup, selector: str, attr: str) -> Optional[str]:
        element = soup.select_one(selector)
        return str(element.get(attr)).strip() if element and element.get(attr) else None

    def _download_public_media(self, url: str, destination: Path) -> None:
        response = self._polite_get(url, stream=True, headers=self._request_headers())
        status = int(getattr(response, "status_code", 200) or 200)
        if status in BACKOFF_STATUSES:
            self._set_source_backoff(status)
        response.raise_for_status()
        with open(destination, "wb") as handle:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    handle.write(chunk)

    def _collect_candidates(self, max_videos: int, page_start: int, max_pages: int, **kwargs: Any) -> List[DesktopHutVideo]:
        max_videos = max(0, int(max_videos or 0))
        page_start = max(1, int(page_start or 1))
        max_pages = max(1, int(max_pages or 1))
        seen: set[str] = set()
        candidates: List[DesktopHutVideo] = []
        for page in range(page_start, page_start + max_pages):
            for item in self._fetch_page(page=page, limit=max_videos or 100, **kwargs):
                key = item.id or item.preview_url
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(item)
                if len(candidates) >= max_videos:
                    return candidates
        return candidates

    def _fetch_page(self, page: int, limit: int, exclude_tag: str, query: Optional[str] = None, category_id: Optional[str] = None, category_name: Optional[str] = None) -> List[DesktopHutVideo]:
        params: Dict[str, Any] = {"type": "2", "sort": "popular", "page": max(1, int(page or 1))}
        if category_id:
            params["category"] = category_id
        if query:
            params["q"] = query
            params["query"] = query
            params["search"] = query
        response = self.session.get(SEARCH_URL, params=params, timeout=self.timeout)
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        cards = soup.select(".wallpaper-card")
        items: List[DesktopHutVideo] = []
        lowered_exclude = str(exclude_tag or "").lower()
        for card in cards:
            video_id = str(card.get("data-id") or "").strip()
            preview_url = str(card.get("data-preview") or "").strip()
            if not preview_url:
                continue
            title_el = card.select_one(".card-title")
            image_el = card.find("img")
            alt_text = str(image_el.get("alt", "") if image_el else "")
            title = title_el.get_text(strip=True) if title_el else alt_text or video_id or "DesktopHut Video"
            if lowered_exclude and (lowered_exclude in title.lower() or lowered_exclude in alt_text.lower()):
                continue
            if query and query.lower() not in f"{title} {alt_text}".lower():
                continue
            items.append(DesktopHutVideo(
                id=video_id or sanitize_filename(title),
                title=title,
                preview_url=urljoin(BASE_URL, preview_url),
                category_id=category_id,
                category_name=category_name,
                page=page,
                alt_text=alt_text,
            ))
            if len(items) >= max(0, int(limit or 0)):
                break
        return items

    def _download_candidates(self, candidates: Iterable[DesktopHutVideo], folder: Path, max_videos: int, overwrite: bool) -> Dict[str, Any]:
        downloaded: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []
        max_videos = max(0, int(max_videos or 0))
        for item in candidates:
            if len(downloaded) >= max_videos:
                break
            filename = f"{sanitize_filename(item.title, fallback=item.id)}.mp4"
            destination = folder / filename
            if destination.exists() and not overwrite:
                skipped.append({**item.to_dict(), "reason": "exists", "file_path": str(destination)})
                continue
            try:
                with self.session.get(item.preview_url, stream=True, timeout=self.timeout) as response:
                    response.raise_for_status()
                    with open(destination, "wb") as handle:
                        for chunk in response.iter_content(chunk_size=1024 * 1024):
                            if chunk:
                                handle.write(chunk)
                downloaded.append({**item.to_dict(), "file_path": str(destination)})
            except Exception as exc:  # noqa: BLE001 - MCP should report per-item failures.
                if destination.exists() and destination.stat().st_size == 0:
                    destination.unlink(missing_ok=True)
                errors.append({**item.to_dict(), "error": str(exc), "file_path": str(destination)})
        return {
            "output_dir": str(folder),
            "downloaded_count": len(downloaded),
            "skipped_count": len(skipped),
            "error_count": len(errors),
            "downloaded": downloaded,
            "skipped": skipped,
            "errors": errors,
        }

    def _prepare_output_dir(self, output_root: str, folder_name: str) -> Path:
        root = Path(os.path.expandvars(os.path.expanduser(output_root or "~/Desktop/Archive"))).resolve()
        folder = root / category_folder_name(folder_name)
        folder.mkdir(parents=True, exist_ok=True)
        return folder


def index_video_directory(db: Session, directory: str, category: str, source_directory_id: Optional[int] = None) -> Dict[str, Any]:
    if not directory:
        raise ValueError("directory is required")
    if not category:
        raise ValueError("category is required")
    ensure_sqlite_schema_compatibility()
    service = VideoService(db, get_twisted_streaming())
    videos = service.scan_directory(directory, category=category, source_directory_id=source_directory_id)
    indexed = [video.to_dict() for video in videos]
    return {
        "success": True,
        "directory": os.path.abspath(os.path.expanduser(directory)),
        "category": category,
        "indexed_count": len(indexed),
        "videos": indexed,
    }
