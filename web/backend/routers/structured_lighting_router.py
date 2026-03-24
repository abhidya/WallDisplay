from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field

from services.structured_lighting_service import get_structured_lighting_service


router = APIRouter(prefix="/api/structured-lighting", tags=["structured-lighting"])


class StructuredLightingSessionCreate(BaseModel):
    name: str = Field(..., description="User-facing calibration session name")
    projector_device_id: Optional[str] = Field(None, description="Target DLNA projector device id")
    camera_index: int = Field(0, ge=0, description="Host-side camera index")
    projector_width: int = Field(1280, ge=2, description="Projector width in pixels")
    projector_height: int = Field(720, ge=2, description="Projector height in pixels")
    presentation_mode: str = Field("dlna_step", description="Pattern presentation mode")
    hold_ms: int = Field(1200, ge=100, le=10000, description="How long each pattern is held before capture")
    notes: Optional[str] = Field(None, description="Optional operator notes")


class StructuredLightingWorkerHeartbeat(BaseModel):
    worker_id: str
    hostname: Optional[str] = None
    camera_indices: List[int] = Field(default_factory=list)
    state: str = "idle"
    message: Optional[str] = None


@router.get("/capabilities")
def get_capabilities() -> Dict:
    return {
        "presentation_modes": [
            {
                "id": "dlna_step",
                "label": "DLNA Step",
                "description": "Cast one pattern at a time, capture, then advance to the next pattern.",
            }
        ],
        "workflow": [
            "Create calibration session",
            "Generate graycode capture plan",
            "Present each pattern to projector",
            "Capture camera frame after each projected pattern settles",
            "Decode captured set into projector-space masks",
        ],
    }


@router.get("/status")
def get_status() -> Dict:
    service = get_structured_lighting_service()
    return service.get_status()


@router.get("/sessions")
def list_sessions() -> List[Dict]:
    service = get_structured_lighting_service()
    return service.list_sessions()


@router.post("/sessions")
def create_session(payload: StructuredLightingSessionCreate) -> Dict:
    service = get_structured_lighting_service()
    return service.create_session(**payload.model_dump())


@router.get("/sessions/{session_id}")
def get_session(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    session = service.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return session


@router.post("/sessions/{session_id}/start")
def start_session(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    session = service.start_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return session


@router.delete("/sessions/{session_id}")
def delete_session(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    deleted = service.delete_session(session_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return {"status": "deleted", "session_id": session_id}


@router.get("/sessions/{session_id}/capture-plan")
def get_capture_plan(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    plan = service.get_capture_plan(session_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return plan


@router.get("/sessions/{session_id}/runtime")
def get_runtime(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    runtime = service.get_runtime(session_id)
    if not runtime:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return runtime


@router.get("/sessions/{session_id}/steps/{step_index}/image")
def get_step_image(session_id: str, step_index: int) -> Response:
    service = get_structured_lighting_service()
    image_bytes = service.render_step_image(session_id, step_index)
    if image_bytes is None:
        raise HTTPException(status_code=404, detail="Structured lighting step not found")
    return Response(content=image_bytes, media_type="image/png")


@router.post("/worker/heartbeat")
def worker_heartbeat(payload: StructuredLightingWorkerHeartbeat) -> Dict:
    service = get_structured_lighting_service()
    return service.update_worker_status(**payload.model_dump())


@router.get("/worker/{worker_id}/next-step")
def claim_next_step(worker_id: str) -> Dict:
    service = get_structured_lighting_service()
    step = service.claim_next_step(worker_id)
    return {"step": step}


@router.post("/sessions/{session_id}/captures")
async def upload_capture(
    session_id: str,
    step_index: int = Form(...),
    capture: UploadFile = File(...),
) -> Dict:
    service = get_structured_lighting_service()
    file_bytes = await capture.read()
    session = service.record_capture(session_id, step_index, file_bytes, capture.filename or "capture.png")
    if not session:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return session
