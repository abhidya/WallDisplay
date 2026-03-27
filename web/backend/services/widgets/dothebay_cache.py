import json
import os
from typing import Any, Dict, Optional


def _cache_path() -> str:
    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    cache_dir = os.path.join(base_dir, "uploads", "widgets")
    os.makedirs(cache_dir, exist_ok=True)
    return os.path.join(cache_dir, "dothebay_lgbtq_cache.json")


def loadDoTheBayCache() -> Optional[Dict[str, Any]]:
    path = _cache_path()
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as handle:
            payload = json.load(handle)
    except Exception:
        return None
    if not isinstance(payload, dict):
        return None
    return payload


def saveDoTheBayCache(payload: Dict[str, Any]) -> Dict[str, Any]:
    path = _cache_path()
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
    return payload
