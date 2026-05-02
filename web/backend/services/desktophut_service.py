"""DesktopHut download/index helpers for agent-facing MCP tools."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from web.backend.core.twisted_streaming import get_instance as get_twisted_streaming
from web.backend.database.database import ensure_sqlite_schema_compatibility
from web.backend.services.video_service import VideoService

BASE_URL = "https://www.desktophut.com"
SEARCH_URL = f"{BASE_URL}/search"
DEFAULT_EXCLUDE_TAG = "Girl"
VIDEO_EXTENSIONS = {".mp4", ".m4v", ".mov", ".mkv", ".webm"}

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


class DesktopHutService:
    def __init__(self, session: Optional[requests.Session] = None, timeout: int = 20):
        self.session = session or requests.Session()
        self.timeout = timeout

    def list_categories(self) -> List[Dict[str, str]]:
        return [{"id": cat_id, "name": name} for cat_id, name in CATEGORIES.items()]

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

    def download_category(
        self,
        category: str,
        output_root: str,
        max_videos: int = 10,
        page_start: int = 1,
        max_pages: int = 3,
        exclude_tag: str = DEFAULT_EXCLUDE_TAG,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        cat_id, cat_name = normalize_category(category)
        folder = self._prepare_output_dir(output_root, category_folder_name(cat_name))
        candidates = self._collect_candidates(
            category_id=cat_id,
            category_name=cat_name,
            page_start=page_start,
            max_pages=max_pages,
            max_videos=max_videos,
            exclude_tag=exclude_tag,
        )
        return self._download_candidates(candidates, folder, max_videos=max_videos, overwrite=overwrite)

    def download_search(
        self,
        query: str,
        output_root: str,
        category: Optional[str] = None,
        folder_name: Optional[str] = None,
        max_videos: int = 10,
        page_start: int = 1,
        max_pages: int = 3,
        exclude_tag: str = DEFAULT_EXCLUDE_TAG,
        overwrite: bool = False,
    ) -> Dict[str, Any]:
        if not str(query or "").strip():
            raise ValueError("query is required")
        cat_id, cat_name = normalize_category(category)
        folder = self._prepare_output_dir(output_root, folder_name or sanitize_filename(query, fallback="search"))
        candidates = self._collect_candidates(
            query=str(query).strip(),
            category_id=cat_id,
            category_name=cat_name,
            page_start=page_start,
            max_pages=max_pages,
            max_videos=max_videos,
            exclude_tag=exclude_tag,
        )
        return self._download_candidates(candidates, folder, max_videos=max_videos, overwrite=overwrite)

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

    def _fetch_page(
        self,
        page: int,
        limit: int,
        exclude_tag: str,
        query: Optional[str] = None,
        category_id: Optional[str] = None,
        category_name: Optional[str] = None,
    ) -> List[DesktopHutVideo]:
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
            title = (title_el.get_text(strip=True) if title_el else alt_text or video_id or "DesktopHut Video")
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

    def _download_candidates(
        self,
        candidates: Iterable[DesktopHutVideo],
        folder: Path,
        max_videos: int,
        overwrite: bool,
    ) -> Dict[str, Any]:
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
