from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


_RECENT_PROJECTOR_REQUESTS: Deque[Dict[str, Any]] = deque(maxlen=100)
_LIVE_PROJECTOR_CLIENTS: Dict[str, Dict[str, Any]] = {}
_LOCK = Lock()
LIVE_PROJECTOR_CLIENT_TTL_SECONDS = 45


def record_projector_request(
    *,
    client_ip: str,
    method: str,
    path: str,
    query: str = "",
    matched_rule_name: Optional[str] = None,
    redirect_target: Optional[str] = None,
    redirected: bool = False,
) -> None:
    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "client_ip": str(client_ip or ""),
        "method": str(method or ""),
        "path": str(path or ""),
        "query": str(query or ""),
        "matched_rule_name": str(matched_rule_name or ""),
        "redirect_target": str(redirect_target or ""),
        "redirected": bool(redirected),
    }
    with _LOCK:
        _RECENT_PROJECTOR_REQUESTS.appendleft(entry)


def get_recent_projector_requests(limit: int = 50) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 50), 100))
    with _LOCK:
        return list(_RECENT_PROJECTOR_REQUESTS)[:safe_limit]


def _build_live_client_key(client_ip: str, path: str, config_id: Optional[int]) -> str:
    normalized_ip = str(client_ip or "").strip()
    normalized_path = str(path or "").strip()
    normalized_config_id = "" if config_id is None else str(int(config_id))
    return f"{normalized_ip}|{normalized_path}|{normalized_config_id}"


def _prune_live_projector_clients_locked(now_ts: float, ttl_seconds: int) -> None:
    stale_keys = [
        key
        for key, entry in _LIVE_PROJECTOR_CLIENTS.items()
        if now_ts - float(entry.get("last_seen_ts") or 0) > ttl_seconds
    ]
    for key in stale_keys:
        _LIVE_PROJECTOR_CLIENTS.pop(key, None)


def record_projector_client_heartbeat(
    *,
    client_ip: str,
    path: str = "",
    query: str = "",
    config_id: Optional[int] = None,
    document_visibility: str = "",
    user_agent: str = "",
) -> Dict[str, Any]:
    now = datetime.now(timezone.utc)
    now_iso = now.isoformat()
    now_ts = now.timestamp()
    normalized_client_ip = str(client_ip or "").strip()
    normalized_path = str(path or "").strip()
    normalized_query = str(query or "").strip()
    normalized_visibility = str(document_visibility or "").strip()
    normalized_user_agent = str(user_agent or "").strip()
    normalized_config_id = None if config_id is None else int(config_id)
    key = _build_live_client_key(normalized_client_ip, normalized_path, normalized_config_id)

    with _LOCK:
        _prune_live_projector_clients_locked(now_ts, LIVE_PROJECTOR_CLIENT_TTL_SECONDS)
        existing = _LIVE_PROJECTOR_CLIENTS.get(key)
        if existing is None:
            existing = {
                "client_ip": normalized_client_ip,
                "path": normalized_path,
                "query": normalized_query,
                "config_id": normalized_config_id,
                "document_visibility": normalized_visibility,
                "user_agent": normalized_user_agent,
                "first_seen_at": now_iso,
                "heartbeat_count": 0,
            }
            _LIVE_PROJECTOR_CLIENTS[key] = existing

        existing.update({
            "client_ip": normalized_client_ip,
            "path": normalized_path,
            "query": normalized_query,
            "config_id": normalized_config_id,
            "document_visibility": normalized_visibility,
            "user_agent": normalized_user_agent,
            "last_seen_at": now_iso,
            "last_seen_ts": now_ts,
            "heartbeat_count": int(existing.get("heartbeat_count") or 0) + 1,
        })

        return {
            key: value
            for key, value in existing.items()
            if key != "last_seen_ts"
        }


def get_live_projector_clients(
    limit: int = 50,
    ttl_seconds: int = LIVE_PROJECTOR_CLIENT_TTL_SECONDS,
) -> List[Dict[str, Any]]:
    safe_limit = max(1, min(int(limit or 50), 100))
    safe_ttl = max(5, int(ttl_seconds or LIVE_PROJECTOR_CLIENT_TTL_SECONDS))
    now_ts = datetime.now(timezone.utc).timestamp()
    with _LOCK:
        _prune_live_projector_clients_locked(now_ts, safe_ttl)
        live_entries = sorted(
            _LIVE_PROJECTOR_CLIENTS.values(),
            key=lambda entry: float(entry.get("last_seen_ts") or 0),
            reverse=True,
        )
        return [
            {
                key: value
                for key, value in entry.items()
                if key != "last_seen_ts"
            }
            for entry in live_entries[:safe_limit]
        ]


def get_recent_live_projector_client(
    client_ip: str,
    ttl_seconds: int = LIVE_PROJECTOR_CLIENT_TTL_SECONDS,
) -> Optional[Dict[str, Any]]:
    normalized_client_ip = str(client_ip or "").strip()
    if not normalized_client_ip:
        return None

    safe_ttl = max(5, int(ttl_seconds or LIVE_PROJECTOR_CLIENT_TTL_SECONDS))
    now_ts = datetime.now(timezone.utc).timestamp()
    with _LOCK:
        _prune_live_projector_clients_locked(now_ts, safe_ttl)
        matches = [
            entry
            for entry in _LIVE_PROJECTOR_CLIENTS.values()
            if entry.get("client_ip") == normalized_client_ip
        ]
        if not matches:
            return None
        latest = max(matches, key=lambda entry: float(entry.get("last_seen_ts") or 0))
        return {
            key: value
            for key, value in latest.items()
            if key != "last_seen_ts"
        }
