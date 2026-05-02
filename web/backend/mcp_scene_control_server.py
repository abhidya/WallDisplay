#!/usr/bin/env python3
"""MCP server for nano-dlna mapping/scene-control automation."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from mcp.types import TextContent

from web.backend.database.database import SessionLocal
from web.backend.services import scene_control_agent_service as scene_tools

logger = logging.getLogger(__name__)
mcp = FastMCP(name="NanoDLNA Scene Control")


def _text(payload: Dict[str, Any]) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True, default=str))]


def _run_db(action):
    db = SessionLocal()
    try:
        return action(db)
    finally:
        db.close()


def _safe(action):
    try:
        return _text({"success": True, "data": action()})
    except Exception as exc:  # noqa: BLE001 - MCP tool should surface clear agent-readable error.
        logger.exception("Scene Control MCP tool failed")
        return _text({"success": False, "error": str(exc), "error_type": type(exc).__name__})


@mcp.tool()
def list_mapping_scenes() -> List[TextContent]:
    """List existing mapping scenes."""
    return _safe(lambda: _run_db(scene_tools.list_mapping_scenes))


@mcp.tool()
def create_mapping_scene(
    name: str,
    canvas_width: int = 1280,
    canvas_height: int = 720,
    groups: Optional[List[Dict[str, Any]]] = None,
    render_settings: Optional[Dict[str, Any]] = None,
) -> List[TextContent]:
    """Create a single mapping scene."""
    return _safe(lambda: _run_db(lambda db: scene_tools.create_mapping_scene(
        db,
        name=name,
        canvas_width=canvas_width,
        canvas_height=canvas_height,
        groups=groups or [],
        render_settings=render_settings or {},
    )))


@mcp.tool()
def add_polygon_mask(scene_id: int, name: str, points: List[Dict[str, float]]) -> List[TextContent]:
    """Add a polygon mask to an existing mapping scene."""
    return _safe(lambda: _run_db(lambda db: scene_tools.add_polygon_mask(db, scene_id, name, points)))


@mcp.tool()
def update_scene_groups(scene_id: int, groups: List[Dict[str, Any]]) -> List[TextContent]:
    """Replace groups for an existing mapping scene."""
    return _safe(lambda: _run_db(lambda db: scene_tools.update_scene_groups(db, scene_id, groups)))


@mcp.tool()
def create_scene_rank(
    name: str,
    scene_ids: List[int],
    gap_px: int = 0,
    orientation: str = "horizontal",
) -> List[TextContent]:
    """Create a rank spanning multiple mapping scenes/clients."""
    return _safe(lambda: _run_db(lambda db: scene_tools.create_scene_rank(
        db,
        name=name,
        scene_ids=scene_ids,
        gap_px=gap_px,
        orientation=orientation,
    )))


@mcp.tool()
def create_scene_control_preset(
    name: str,
    scene_ids: List[int],
    group_assignments: Optional[Dict[str, List[List[str]]]] = None,
    row_edits: Optional[Dict[str, Dict[str, Any]]] = None,
    rank_id: Optional[int] = None,
    preset_metadata: Optional[Dict[str, Any]] = None,
) -> List[TextContent]:
    """Create a scene-control preset for scenes, group assignments, and row edits."""
    return _safe(lambda: _run_db(lambda db: scene_tools.create_scene_control_preset(
        db,
        name=name,
        scene_ids=scene_ids,
        group_assignments=group_assignments or {},
        row_edits=row_edits or {},
        rank_id=rank_id,
        preset_metadata=preset_metadata or {},
    )))


@mcp.tool()
def create_scene_across_clients(
    name: str,
    clients: List[Dict[str, Any]],
    group_template: Optional[List[Dict[str, Any]]] = None,
    gap_px: int = 0,
    create_preset: bool = True,
) -> List[TextContent]:
    """Create one mapping scene per client/display, plus rank/preset metadata."""
    return _safe(lambda: _run_db(lambda db: scene_tools.create_scene_across_clients(
        db,
        name=name,
        clients=clients,
        group_template=group_template or [],
        gap_px=gap_px,
        create_preset=create_preset,
    )))


@mcp.tool()
def create_all_walls_scene_from_media(
    name: str,
    clients: List[Dict[str, Any]],
    background_video_ids: List[int],
    pattern_layers: Optional[List[Dict[str, Any]]] = None,
    gap_px: int = 0,
    create_preset: bool = True,
    use_media_list: bool = False,
) -> List[TextContent]:
    """Create all-wall scenes with fish/video backgrounds and pattern layers above them."""
    return _safe(lambda: _run_db(lambda db: scene_tools.create_all_walls_scene_from_media(
        db,
        name=name,
        clients=clients,
        background_video_ids=background_video_ids,
        pattern_layers=pattern_layers or [],
        gap_px=gap_px,
        create_preset=create_preset,
        use_media_list=use_media_list,
    )))


async def main() -> None:
    await mcp.run_stdio()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
