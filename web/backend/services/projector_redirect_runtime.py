from collections import deque
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Deque, Dict, List, Optional


_RECENT_PROJECTOR_REQUESTS: Deque[Dict[str, Any]] = deque(maxlen=100)
_LOCK = Lock()


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
