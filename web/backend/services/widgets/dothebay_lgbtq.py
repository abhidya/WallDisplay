import logging
import re
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import requests

try:
    from bs4 import BeautifulSoup
except ImportError:  # optional dependency
    BeautifulSoup = None

from web.backend.services.widgets.dothebay_cache import loadDoTheBayCache, saveDoTheBayCache

logger = logging.getLogger(__name__)

DOTHEBAY_LGBTQ_URL = "https://dothebay.com/events/lgbtq/today"
DOTHEBAY_STALE_AFTER = timedelta(hours=6)


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        if value.endswith("Z"):
            value = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _extract_background_image(style_value: str) -> str:
    if not style_value:
        return ""
    match = re.search(r"background-image\s*:\s*url\((['\"]?)(.*?)\1\)", style_value, re.IGNORECASE)
    return match.group(2).strip() if match else ""


def _clean_text(node) -> str:
    if not node:
        return ""
    return " ".join(node.get_text(" ", strip=True).split())


def scrapeDoTheBayLgbtq() -> List[Dict[str, Any]]:
    if BeautifulSoup is None:
        raise RuntimeError("beautifulsoup4 is required for DoTheBay widget scraping")

    response = requests.get(
        DOTHEBAY_LGBTQ_URL,
        timeout=20,
        headers={
            "User-Agent": "Mozilla/5.0 (compatible; nano-dlna widget scraper)",
            "Accept-Language": "en-US,en;q=0.9",
        },
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    cards = soup.select(".ds-listing.event-card.ds-event-category-lgbtq")
    events: List[Dict[str, Any]] = []
    seen_keys = set()

    for card in cards:
        title_link = card.select_one("a.ds-listing-event-title")
        title = _clean_text(card.select_one(".ds-listing-event-title-text")) or _clean_text(title_link)
        href = title_link.get("href") if title_link else ""
        event_url = urljoin(DOTHEBAY_LGBTQ_URL, href) if href else ""
        image_url = _extract_background_image((card.select_one(".ds-cover-image") or {}).get("style", ""))
        venue = _clean_text(card.select_one(".ds-venue-name [itemprop='name']")) or _clean_text(card.select_one(".ds-venue-name"))
        datetime_text = _clean_text(card.select_one(".ds-event-time"))
        summary = _clean_text(card.select_one(".ds-byline"))
        start_date = ""
        start_meta = card.select_one("meta[itemprop='startDate']")
        if start_meta:
            start_date = (start_meta.get("content") or start_meta.get("datetime") or "").strip()

        if not title or not event_url:
            continue

        dedupe_key = (event_url.lower(), start_date or datetime_text.lower())
        if dedupe_key in seen_keys:
            continue
        seen_keys.add(dedupe_key)

        events.append(
            {
                "title": title,
                "eventUrl": event_url,
                "imageUrl": image_url,
                "dateTimeText": datetime_text,
                "venue": venue,
                "summary": summary if summary and summary != title else "",
                "startDate": start_date,
            }
        )

    return events


def getDoTheBayWidgetData() -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    cached = loadDoTheBayCache()
    cached_fetched_at = _parse_iso((cached or {}).get("fetchedAt"))
    cache_is_fresh = bool(cached_fetched_at and now - cached_fetched_at < DOTHEBAY_STALE_AFTER)

    if cached and cache_is_fresh:
        return {
            "source": cached.get("source", DOTHEBAY_LGBTQ_URL),
            "fetchedAt": cached.get("fetchedAt"),
            "stale": False,
            "events": cached.get("events", []),
        }

    try:
        events = scrapeDoTheBayLgbtq()
        payload = {
            "source": DOTHEBAY_LGBTQ_URL,
            "fetchedAt": now.isoformat(),
            "stale": False,
            "events": events,
        }
        saveDoTheBayCache(payload)
        return payload
    except Exception as exc:
        logger.warning("DoTheBay LGBTQ scrape failed: %s", exc)
        if cached:
            return {
                "source": cached.get("source", DOTHEBAY_LGBTQ_URL),
                "fetchedAt": cached.get("fetchedAt"),
                "stale": True,
                "events": cached.get("events", []),
                "error": str(exc),
            }
        return {
            "source": DOTHEBAY_LGBTQ_URL,
            "fetchedAt": None,
            "stale": True,
            "events": [],
            "error": str(exc),
        }
