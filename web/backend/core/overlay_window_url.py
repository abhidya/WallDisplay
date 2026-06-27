from typing import Any, Dict, Optional
from urllib.parse import urlencode


def build_overlay_window_url(
    base_url: str,
    *,
    config_id: Optional[int] = None,
    controls_hidden: bool = False,
    hide_widgets: bool = False,
    capture_mode: Optional[str] = None,
    projector_id: Optional[str] = None,
    mode: Optional[str] = None,
    extra_params: Optional[Dict[str, Any]] = None,
) -> str:
    params: Dict[str, Any] = {}
    if projector_id:
        params["projector_id"] = projector_id
    if mode:
        params["mode"] = mode
    if config_id is not None:
        params["config_id"] = config_id
    if controls_hidden:
        params["controls"] = "hidden"
    if hide_widgets:
        params["widgets"] = "hidden"
    if capture_mode:
        params["capture"] = capture_mode
    for key, value in (extra_params or {}).items():
        if value is not None and key not in params:
            params[key] = value
    return f"{base_url.rstrip('/')}/backend-static/overlay_window.html?{urlencode(_url_param_value(params))}"


def _url_param_value(params: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: str(value).lower() if isinstance(value, bool) else value
        for key, value in params.items()
    }
