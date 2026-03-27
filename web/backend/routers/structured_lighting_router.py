from typing import Dict, List, Optional

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse, Response
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


class StructuredLightingWorkerStartRequest(BaseModel):
    base_url: str = Field("http://localhost:8000")
    camera_index: int = Field(0, ge=0)
    projector_screen_x: int = Field(1280)
    projector_screen_y: int = Field(0)
    projector_width: int = Field(1280, ge=2)
    projector_height: int = Field(720, ge=2)
    settle_seconds: float = Field(1.0, ge=0.0, le=10.0)
    flush_count: int = Field(30, ge=0, le=120)
    pump_ms: int = Field(400, ge=1, le=2000)
    poll_seconds: float = Field(1.0, ge=0.1, le=10.0)


class StructuredLightingDecodeRequest(BaseModel):
    sample_step: int = Field(1, ge=1, le=16, description="Decode every Nth camera pixel")
    tuning_params: Optional[Dict[str, float]] = Field(None, description="Optional decode/mask tuning parameters")


class StructuredLightingParameterSearchRequest(BaseModel):
    sample_step: int = Field(1, ge=1, le=16, description="Decode every Nth camera pixel for search candidates")


class StructuredLightingReviewUpdate(BaseModel):
    verdict: str = Field(..., pattern="^(accepted|needs_recapture)$")
    notes: Optional[str] = Field(None, description="Optional operator notes about the review verdict")
    reviewed_by: Optional[str] = Field(None, description="Operator name or identifier")


class StructuredLightingPublishRequest(BaseModel):
    scene_name: Optional[str] = Field(None, description="Optional name for the new mapping scene")


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


@router.get("/sessions/{session_id}/captures")
def list_captures(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    captures = service.list_captures(session_id)
    if not captures:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return captures


@router.post("/sessions/{session_id}/decode")
def decode_session(session_id: str, payload: StructuredLightingDecodeRequest) -> Dict:
    service = get_structured_lighting_service()
    session = service.decode_session(
        session_id,
        sample_step=payload.sample_step,
        tuning_params=payload.tuning_params,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return session


@router.post("/sessions/{session_id}/tuning-search")
def run_tuning_search(session_id: str, payload: StructuredLightingParameterSearchRequest) -> Dict:
    service = get_structured_lighting_service()
    try:
        result = service.run_tuning_search(session_id, sample_step=payload.sample_step)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return result


@router.get("/sessions/{session_id}/tuning-search")
def get_tuning_search(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    result = service.get_tuning_search(session_id)
    if not result:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return result


@router.get("/sessions/{session_id}/tuning-search/{candidate_id}/previews/{preview_name}")
def get_tuning_search_preview(session_id: str, candidate_id: str, preview_name: str) -> Response:
    service = get_structured_lighting_service()
    preview_bytes = service.render_tuning_search_preview(session_id, candidate_id, preview_name)
    if preview_bytes is None:
        raise HTTPException(status_code=404, detail="Structured lighting tuning preview not found")
    return Response(content=preview_bytes, media_type="image/png")


@router.get("/sessions/{session_id}/calibration")
def get_calibration(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    calibration = service.get_calibration(session_id)
    if not calibration:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return calibration


@router.get("/sessions/{session_id}/artifacts/review")
def get_artifact_review(session_id: str) -> Dict:
    service = get_structured_lighting_service()
    review = service.get_artifact_review(session_id)
    if not review:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return review


@router.get("/sessions/{session_id}/artifacts/previews/{preview_id}")
def get_artifact_preview(session_id: str, preview_id: str) -> Response:
    service = get_structured_lighting_service()
    preview_bytes = service.render_artifact_preview(session_id, preview_id)
    if preview_bytes is None:
        raise HTTPException(status_code=404, detail="Structured lighting artifact preview not found")
    return Response(content=preview_bytes, media_type="image/png")


@router.post("/sessions/{session_id}/review")
def update_review(session_id: str, payload: StructuredLightingReviewUpdate) -> Dict:
    service = get_structured_lighting_service()
    session = service.update_review(
        session_id,
        verdict=payload.verdict,
        notes=payload.notes,
        reviewed_by=payload.reviewed_by,
    )
    if not session:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return session


@router.get("/sessions/{session_id}/export")
def export_session(session_id: str):
    service = get_structured_lighting_service()
    try:
        export_info = service.export_session_bundle(session_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not export_info:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return FileResponse(
        export_info["export_path"],
        media_type="application/zip",
        filename=export_info["filename"],
    )


@router.post("/sessions/{session_id}/publish-mapping-scene")
def publish_mapping_scene(session_id: str, payload: StructuredLightingPublishRequest) -> Dict:
    service = get_structured_lighting_service()
    try:
        result = service.publish_mapping_scene(session_id, scene_name=payload.scene_name)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if not result:
        raise HTTPException(status_code=404, detail="Structured lighting session not found")
    return result


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


@router.post("/worker/start")
def start_worker(payload: StructuredLightingWorkerStartRequest) -> Dict:
    service = get_structured_lighting_service()
    return service.start_worker(**payload.model_dump())


@router.post("/worker/stop")
def stop_worker() -> Dict:
    service = get_structured_lighting_service()
    return service.stop_worker()


@router.get("/worker/{worker_id}/control")
def get_worker_control(worker_id: str) -> Dict:
    service = get_structured_lighting_service()
    return service.get_worker_control(worker_id)


@router.post("/worker/{worker_id}/confirm-ready")
def confirm_worker_ready(worker_id: str) -> Dict:
    service = get_structured_lighting_service()
    try:
        return service.confirm_worker_ready(worker_id)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
