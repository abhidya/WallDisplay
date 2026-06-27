#!/usr/bin/env python3
"""MCP server for HDMI structured-lighting calibration and mapping projection."""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, List, Optional

import requests
from fastmcp import FastMCP
from mcp.types import TextContent

logger = logging.getLogger(__name__)
mcp = FastMCP(name="NanoDLNA Structured Lighting")

DEFAULT_BASE_URL = os.environ.get("WALLDISPLAY_BASE_URL", "http://127.0.0.1:8088")


def _text(payload: Dict[str, Any]) -> List[TextContent]:
    return [TextContent(type="text", text=json.dumps(payload, indent=2, sort_keys=True, default=str))]


def _request_json(
    method: str,
    path: str,
    *,
    base_url: str = DEFAULT_BASE_URL,
    params: Optional[Dict[str, Any]] = None,
    payload: Optional[Dict[str, Any]] = None,
    timeout: float = 60,
) -> Dict[str, Any]:
    url = f"{base_url.rstrip('/')}{path}"
    response = requests.request(method, url, params=params, json=payload, timeout=timeout)
    try:
        body = response.json()
    except ValueError:
        body = {"text": response.text}
    if response.status_code >= 400:
        detail = body.get("detail") if isinstance(body, dict) else response.text
        raise RuntimeError(f"{method} {path} failed with {response.status_code}: {detail}")
    return body


def _safe(action):
    try:
        return _text({"success": True, "data": action()})
    except Exception as exc:  # noqa: BLE001 - MCP tools should return agent-readable errors.
        logger.exception("Structured Lighting MCP tool failed")
        return _text({"success": False, "error": str(exc), "error_type": type(exc).__name__})


def _worker_process_running(worker: Dict[str, Any]) -> bool:
    return worker.get("process_state") in {"starting", "running"} or bool(worker.get("process_pid"))


@mcp.tool()
def structured_lighting_status(base_url: str = DEFAULT_BASE_URL) -> List[TextContent]:
    """Return structured-lighting worker/session status from the running WallDisplay service."""
    return _safe(lambda: _request_json("GET", "/api/structured-lighting/status", base_url=base_url))


@mcp.tool()
def hdmi_preflight(
    projector_id: str = "proj-hdmi-local",
    camera_index: int = 0,
    base_url: str = DEFAULT_BASE_URL,
) -> List[TextContent]:
    """Resolve HDMI projector geometry and recommended worker/session defaults."""
    return _safe(lambda: _request_json(
        "GET",
        "/api/structured-lighting/hdmi-preflight",
        base_url=base_url,
        params={
            "projector_id": projector_id,
            "camera_index": camera_index,
            "base_url": base_url,
        },
    ))


@mcp.tool()
def start_hdmi_worker(
    projector_id: str = "proj-hdmi-local",
    camera_index: int = 0,
    base_url: str = DEFAULT_BASE_URL,
    force_restart: bool = False,
) -> List[TextContent]:
    """Start the local capture worker using HDMI preflight geometry."""
    def action():
        preflight = _request_json(
            "GET",
            "/api/structured-lighting/hdmi-preflight",
            base_url=base_url,
            params={"projector_id": projector_id, "camera_index": camera_index, "base_url": base_url},
        )
        if preflight.get("status") != "ready":
            return {"stage": "preflight_failed", "preflight": preflight}

        worker = preflight.get("worker") or {}
        if force_restart and _worker_process_running(worker):
            _request_json("POST", "/api/structured-lighting/worker/stop", base_url=base_url)
        elif _worker_process_running(worker):
            return {"stage": "worker_already_running", "preflight": preflight, "worker": worker}

        started = _request_json(
            "POST",
            "/api/structured-lighting/worker/start",
            base_url=base_url,
            payload=preflight["recommended_worker"],
        )
        return {"stage": "worker_start_requested", "preflight": preflight, "worker": started}

    return _safe(action)


@mcp.tool()
def confirm_hdmi_worker_ready(worker_id: Optional[str] = None, base_url: str = DEFAULT_BASE_URL) -> List[TextContent]:
    """Confirm camera framing after the operator has verified the native preview."""
    def action():
        status = _request_json("GET", "/api/structured-lighting/status", base_url=base_url)
        target_worker_id = worker_id or status.get("worker", {}).get("worker_id")
        if not target_worker_id:
            raise RuntimeError("No structured-lighting worker id is available to confirm.")
        return _request_json(
            "POST",
            f"/api/structured-lighting/worker/{target_worker_id}/confirm-ready",
            base_url=base_url,
        )

    return _safe(action)


@mcp.tool()
def create_hdmi_calibration_session(
    name: str = "Agentic HDMI Calibration",
    projector_id: str = "proj-hdmi-local",
    camera_index: int = 0,
    base_url: str = DEFAULT_BASE_URL,
) -> List[TextContent]:
    """Create an HDMI Step Gray-code structured-lighting session from preflight defaults."""
    def action():
        preflight = _request_json(
            "GET",
            "/api/structured-lighting/hdmi-preflight",
            base_url=base_url,
            params={"projector_id": projector_id, "camera_index": camera_index, "base_url": base_url},
        )
        if preflight.get("status") != "ready":
            return {"stage": "preflight_failed", "preflight": preflight}
        payload = {
            **preflight["recommended_session"],
            "name": name,
            "projector_device_id": projector_id,
            "notes": "Created by structured-lighting MCP.",
        }
        session = _request_json("POST", "/api/structured-lighting/sessions", base_url=base_url, payload=payload)
        return {"stage": "session_created", "preflight": preflight, "session": session}

    return _safe(action)


@mcp.tool()
def start_capture_session(session_id: str, base_url: str = DEFAULT_BASE_URL) -> List[TextContent]:
    """Start an existing structured-lighting capture session."""
    return _safe(lambda: _request_json(
        "POST",
        f"/api/structured-lighting/sessions/{session_id}/start",
        base_url=base_url,
        timeout=120,
    ))


@mcp.tool()
def decode_calibration_session(session_id: str, sample_step: int = 1, base_url: str = DEFAULT_BASE_URL) -> List[TextContent]:
    """Decode a captured structured-lighting session."""
    return _safe(lambda: _request_json(
        "POST",
        f"/api/structured-lighting/sessions/{session_id}/decode",
        base_url=base_url,
        payload={"sample_step": sample_step},
        timeout=300,
    ))


@mcp.tool()
def accept_calibration_session(
    session_id: str,
    reviewed_by: str = "structured-lighting-mcp",
    notes: str = "Accepted by agent after artifact review.",
    base_url: str = DEFAULT_BASE_URL,
) -> List[TextContent]:
    """Accept a decoded session so it can be exported or published to Mapping."""
    return _safe(lambda: _request_json(
        "POST",
        f"/api/structured-lighting/sessions/{session_id}/review",
        base_url=base_url,
        payload={"verdict": "accepted", "reviewed_by": reviewed_by, "notes": notes},
    ))


@mcp.tool()
def publish_calibration_mapping_scene(
    session_id: str,
    scene_name: Optional[str] = None,
    animation_id: str = "neural_noise",
    base_url: str = DEFAULT_BASE_URL,
) -> List[TextContent]:
    """Publish accepted calibration masks into a Mapping scene with animation groups."""
    return _safe(lambda: _request_json(
        "POST",
        f"/api/structured-lighting/sessions/{session_id}/publish-mapping-scene",
        base_url=base_url,
        payload={
            "scene_name": scene_name,
            "animation_id": animation_id,
            "create_animation_groups": True,
        },
    ))


@mcp.tool()
def project_mapping_scene_to_hdmi(
    scene_id: int,
    projector_id: str = "proj-hdmi-local",
    base_url: str = DEFAULT_BASE_URL,
    controls_hidden: bool = True,
) -> List[TextContent]:
    """Launch a Mapping scene through the HDMI overlay renderer."""
    return _safe(lambda: _request_json(
        "POST",
        f"/api/mappings/scenes/{int(scene_id)}/project",
        base_url=base_url,
        payload={
            "target_type": "hdmi",
            "target_id": projector_id,
            "overlay_base_url": base_url,
            "controls_hidden": controls_hidden,
        },
    ))


@mcp.tool()
def stop_hdmi_projection(projector_id: str = "proj-hdmi-local", base_url: str = DEFAULT_BASE_URL) -> List[TextContent]:
    """Stop HDMI mapping projection."""
    return _safe(lambda: _request_json(
        "POST",
        "/api/mappings/scenes/project/stop",
        base_url=base_url,
        payload={"target_type": "hdmi", "target_id": projector_id},
    ))


@mcp.tool()
def run_hdmi_structured_lighting_pipeline(
    projector_id: str = "proj-hdmi-local",
    camera_index: int = 0,
    session_name: str = "Agentic HDMI Calibration",
    session_id: Optional[str] = None,
    animation_id: str = "neural_noise",
    base_url: str = DEFAULT_BASE_URL,
    confirm_operator_ready: bool = False,
    project_when_published: bool = False,
) -> List[TextContent]:
    """
    Drive the HDMI structured-lighting workflow until it reaches the next required state.

    If the worker is awaiting camera confirmation, this returns stage
    `awaiting_operator_confirmation` unless confirm_operator_ready is true.
    """
    def action():
        preflight = _request_json(
            "GET",
            "/api/structured-lighting/hdmi-preflight",
            base_url=base_url,
            params={"projector_id": projector_id, "camera_index": camera_index, "base_url": base_url},
        )
        if preflight.get("status") != "ready":
            return {"stage": "preflight_failed", "preflight": preflight}

        status = _request_json("GET", "/api/structured-lighting/status", base_url=base_url)
        worker = status.get("worker") or {}
        if not _worker_process_running(worker):
            started = _request_json(
                "POST",
                "/api/structured-lighting/worker/start",
                base_url=base_url,
                payload=preflight["recommended_worker"],
            )
            return {"stage": "worker_start_requested", "preflight": preflight, "worker": started}

        if worker.get("state") == "awaiting_operator" and not confirm_operator_ready:
            return {"stage": "awaiting_operator_confirmation", "preflight": preflight, "worker": worker}
        if worker.get("state") == "awaiting_operator" and confirm_operator_ready:
            worker = _request_json(
                "POST",
                f"/api/structured-lighting/worker/{worker['worker_id']}/confirm-ready",
                base_url=base_url,
            )

        if not session_id:
            payload = {
                **preflight["recommended_session"],
                "name": session_name,
                "projector_device_id": projector_id,
                "notes": "Created by structured-lighting MCP pipeline.",
            }
            session = _request_json("POST", "/api/structured-lighting/sessions", base_url=base_url, payload=payload)
            return {"stage": "session_created", "preflight": preflight, "worker": worker, "session": session}

        runtime = _request_json("GET", f"/api/structured-lighting/sessions/{session_id}/runtime", base_url=base_url)
        session = runtime.get("session") or {}
        if session.get("status") in {"draft", "ready", "waiting_for_worker"}:
            started = _request_json(
                "POST",
                f"/api/structured-lighting/sessions/{session_id}/start",
                base_url=base_url,
                timeout=120,
            )
            return {"stage": "capture_started", "preflight": preflight, "worker": worker, "session": started}
        if session.get("status") == "capturing":
            return {"stage": "capture_in_progress", "preflight": preflight, "worker": worker, "runtime": runtime}
        if session.get("status") != "completed":
            return {"stage": "session_not_ready", "preflight": preflight, "worker": worker, "runtime": runtime}

        if session.get("decode", {}).get("status") != "completed":
            decoded = _request_json(
                "POST",
                f"/api/structured-lighting/sessions/{session_id}/decode",
                base_url=base_url,
                payload={"sample_step": 1},
                timeout=300,
            )
            return {"stage": "decoded", "preflight": preflight, "session": decoded}

        if session.get("review", {}).get("status") != "accepted":
            accepted = _request_json(
                "POST",
                f"/api/structured-lighting/sessions/{session_id}/review",
                base_url=base_url,
                payload={
                    "verdict": "accepted",
                    "reviewed_by": "structured-lighting-mcp",
                    "notes": "Accepted by agent after decode completion.",
                },
            )
            return {"stage": "accepted", "preflight": preflight, "session": accepted}

        published = _request_json(
            "POST",
            f"/api/structured-lighting/sessions/{session_id}/publish-mapping-scene",
            base_url=base_url,
            payload={
                "scene_name": session_name,
                "animation_id": animation_id,
                "create_animation_groups": True,
            },
        )
        result = {"stage": "published", "preflight": preflight, "published": published}
        if project_when_published:
            result["projection"] = _request_json(
                "POST",
                f"/api/mappings/scenes/{published['scene_id']}/project",
                base_url=base_url,
                payload={
                    "target_type": "hdmi",
                    "target_id": projector_id,
                    "overlay_base_url": base_url,
                    "controls_hidden": True,
                },
            )
        return result

    return _safe(action)


async def main() -> None:
    await mcp.run_stdio()


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
