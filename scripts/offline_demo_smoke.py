#!/usr/bin/env python3
"""Offline demo smoke for WallDisplay's hardware-gated workspace."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def read(path: Path) -> str:
    require(path.exists(), f"missing {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def main() -> None:
    backend_files = [
        "web/backend/main.py",
        "web/backend/services/app_runtime.py",
        "web/backend/services/overlay_cast_service.py",
        "web/backend/services/structured_lighting_service.py",
        "web/backend/static/overlay_window.html",
        "web/backend/static/projection_mapping_tool.html",
    ]
    for rel in backend_files:
        read(ROOT / rel)

    frontend_package = json.loads(read(ROOT / "web/frontend/package.json"))
    mobile_package = json.loads(read(ROOT / "mobile-app/package.json"))
    require("build" in frontend_package.get("scripts", {}), "frontend build script missing")
    require("typecheck" in mobile_package.get("scripts", {}), "mobile typecheck script missing")

    app_js = read(ROOT / "web/frontend/src/App.js")
    routes = sorted(set(part.split('"', 1)[0] for part in app_js.split('path="')[1:]))
    require("/overlay" in routes, "overlay route missing from dashboard")
    require("/structured-lighting" in routes, "structured-lighting route missing from dashboard")

    templates = sorted((ROOT / "nanodlna" / "templates").glob("action-*.xml"))
    require(len(templates) >= 5, f"expected DLNA action templates, found {len(templates)}")

    static_pages = sorted((ROOT / "web" / "backend" / "static").glob("*.html"))
    print("OFFLINE WALLDISPLAY DEMO OK")
    print(f"dashboard_routes={len(routes)} sample={', '.join(routes[:6])}")
    print(f"static_backend_pages={len(static_pages)} dlna_templates={len(templates)}")
    print("demo_path=python3 scripts/offline_demo_smoke.py; hardware demos require LAN devices, Chrome/Playwright, FFmpeg, or cameras")


if __name__ == "__main__":
    main()
