#!/usr/bin/env python3
"""MCP server for bounded DesktopHut ingestion into nano-dlna."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastmcp import FastMCP
from mcp.types import TextContent

from web.backend.database.database import SessionLocal
from web.backend.models.video import VideoModel
from web.backend.services.desktophut_service import DesktopHutService, index_video_directory as index_local_video_directory
from web.backend.services import scene_control_agent_service as scene_tools

logger = logging.getLogger(__name__)
mcp = FastMCP(name="NanoDLNA DesktopHut")


def _text(payload: Dict[str, Any]) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True, default=str))]


def _safe(action):
    try:
        return _text({"success": True, "data": action()})
    except Exception as exc:  # noqa: BLE001 - MCP tool should surface clear agent-readable error.
        logger.exception("DesktopHut MCP tool failed")
        return _text({"success": False, "error": str(exc), "error_type": type(exc).__name__})


def _run_db(action):
    db = SessionLocal()
    try:
        return action(db)
    finally:
        db.close()


def _video_records_under_directory(db, directory: str) -> List[Dict[str, Any]]:
    root = str(Path(os.path.expandvars(os.path.expanduser(directory))).resolve())
    rows = db.query(VideoModel).filter(VideoModel.path.like(f"{root}%")).order_by(VideoModel.id.asc()).all()
    return [row.to_dict() for row in rows]


@mcp.tool()
def list_desktophut_categories() -> List[TextContent]:
    """List known DesktopHut category IDs and names."""
    return _safe(lambda: DesktopHutService().list_categories())


@mcp.tool()
def preview_desktophut_category(
    category: str,
    page: int = 1,
    limit: int = 20,
    exclude_tag: str = "Girl",
) -> List[TextContent]:
    """Preview DesktopHut videos from one category without downloading."""
    return _safe(lambda: DesktopHutService().preview_category(
        category=category,
        page=page,
        limit=limit,
        exclude_tag=exclude_tag,
    ))


@mcp.tool()
def search_desktophut_videos(
    query: str,
    category: Optional[str] = None,
    page: int = 1,
    limit: int = 20,
    exclude_tag: str = "Girl",
) -> List[TextContent]:
    """Search DesktopHut live wallpapers by keyword, optionally constrained by category."""
    return _safe(lambda: DesktopHutService().search_videos(
        query=query,
        category=category,
        page=page,
        limit=limit,
        exclude_tag=exclude_tag,
    ))


@mcp.tool()
def download_desktophut_category(
    category: str,
    output_root: str = "~/Desktop/Archive",
    max_videos: int = 10,
    page_start: int = 1,
    max_pages: int = 3,
    exclude_tag: str = "Girl",
    overwrite: bool = False,
) -> List[TextContent]:
    """Download a bounded number of DesktopHut videos from one category."""
    return _safe(lambda: DesktopHutService().download_category(
        category=category,
        output_root=output_root,
        max_videos=max_videos,
        page_start=page_start,
        max_pages=max_pages,
        exclude_tag=exclude_tag,
        overwrite=overwrite,
    ))


@mcp.tool()
def download_desktophut_search(
    query: str,
    category: Optional[str] = None,
    output_root: str = "~/Desktop/Archive",
    folder_name: Optional[str] = None,
    max_videos: int = 10,
    page_start: int = 1,
    max_pages: int = 3,
    exclude_tag: str = "Girl",
    overwrite: bool = False,
) -> List[TextContent]:
    """Download a bounded number of DesktopHut videos matching a keyword search."""
    return _safe(lambda: DesktopHutService().download_search(
        query=query,
        category=category,
        output_root=output_root,
        folder_name=folder_name,
        max_videos=max_videos,
        page_start=page_start,
        max_pages=max_pages,
        exclude_tag=exclude_tag,
        overwrite=overwrite,
    ))


@mcp.tool()
def index_video_directory(
    directory: str,
    category: str,
    source_directory_id: Optional[int] = None,
) -> List[TextContent]:
    """Index a local directory of videos into nano-dlna under a category."""
    return _safe(lambda: _run_db(lambda db: index_local_video_directory(
        db,
        directory=directory,
        category=category,
        source_directory_id=source_directory_id,
    )))


@mcp.tool()
def download_and_index_desktophut_category(
    category: str,
    library_category: Optional[str] = None,
    output_root: str = "~/Desktop/Archive",
    max_videos: int = 10,
    page_start: int = 1,
    max_pages: int = 3,
    exclude_tag: str = "Girl",
    overwrite: bool = False,
    source_directory_id: Optional[int] = None,
) -> List[TextContent]:
    """Download DesktopHut category videos, then index output directory into nano-dlna."""
    def action():
        downloaded = DesktopHutService().download_category(
            category=category,
            output_root=output_root,
            max_videos=max_videos,
            page_start=page_start,
            max_pages=max_pages,
            exclude_tag=exclude_tag,
            overwrite=overwrite,
        )
        output_dir = downloaded["output_dir"]
        db_result = _run_db(lambda db: {
            "index": index_local_video_directory(db, output_dir, library_category or category, source_directory_id),
            "records": _video_records_under_directory(db, output_dir),
        })
        return {"download": downloaded, **db_result}
    return _safe(action)


@mcp.tool()
def download_and_index_desktophut_search(
    query: str,
    library_category: Optional[str] = None,
    category: Optional[str] = None,
    output_root: str = "~/Desktop/Archive",
    folder_name: Optional[str] = None,
    max_videos: int = 10,
    page_start: int = 1,
    max_pages: int = 3,
    exclude_tag: str = "Girl",
    overwrite: bool = False,
    source_directory_id: Optional[int] = None,
) -> List[TextContent]:
    """Download DesktopHut search results, then index output directory into nano-dlna."""
    def action():
        downloaded = DesktopHutService().download_search(
            query=query,
            category=category,
            output_root=output_root,
            folder_name=folder_name,
            max_videos=max_videos,
            page_start=page_start,
            max_pages=max_pages,
            exclude_tag=exclude_tag,
            overwrite=overwrite,
        )
        output_dir = downloaded["output_dir"]
        db_result = _run_db(lambda db: {
            "index": index_local_video_directory(db, output_dir, library_category or query, source_directory_id),
            "records": _video_records_under_directory(db, output_dir),
        })
        return {"download": downloaded, **db_result}
    return _safe(action)


@mcp.tool()
def download_fish_and_create_wall_scene(
    clients: List[Dict[str, Any]],
    scene_name: str = "Fish Walls",
    query: str = "fish",
    output_root: str = "~/Desktop/Archive",
    max_videos: int = 12,
    max_pages: int = 3,
    pattern_layers: Optional[List[Dict[str, Any]]] = None,
    gap_px: int = 0,
    use_media_list: bool = True,
    exclude_tag: str = "Girl",
) -> List[TextContent]:
    """Download/index fish videos and create all-wall scenes with fish backgrounds and pattern layers."""
    def action():
        downloaded = DesktopHutService().download_search(
            query=query,
            output_root=output_root,
            folder_name="fish",
            max_videos=max_videos,
            max_pages=max_pages,
            exclude_tag=exclude_tag,
        )
        output_dir = downloaded["output_dir"]
        def db_action(db):
            index_result = index_local_video_directory(db, output_dir, "fish")
            records = _video_records_under_directory(db, output_dir)
            video_ids = [int(record["id"]) for record in records]
            if not video_ids:
                raise ValueError("No indexed fish videos available after download")
            scene_result = scene_tools.create_all_walls_scene_from_media(
                db,
                name=scene_name,
                clients=clients,
                background_video_ids=video_ids,
                pattern_layers=pattern_layers or [],
                gap_px=gap_px,
                create_preset=True,
                use_media_list=use_media_list,
            )
            return {"index": index_result, "records": records, "scene": scene_result}
        db_result = _run_db(db_action)
        return {"download": downloaded, **db_result}
    return _safe(action)


async def main() -> None:
    await mcp.run_stdio()


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
