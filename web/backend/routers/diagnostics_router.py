from fastapi import APIRouter, HTTPException, Query

from web.backend.services.service_diagnostics_service import get_service_diagnostics_service


router = APIRouter(prefix="/api/diagnostics", tags=["diagnostics"])


@router.get("/service")
async def get_service_diagnostics(
    incident_limit: int = Query(10, ge=1, le=100),
    run_limit: int = Query(10, ge=1, le=100),
    supervisor_limit: int = Query(10, ge=1, le=100),
):
    service = get_service_diagnostics_service()
    return service.get_service_snapshot(
        incident_limit=incident_limit,
        run_limit=run_limit,
        supervisor_limit=supervisor_limit,
    )


@router.get("/incidents/{incident_id}")
async def get_service_incident_detail(
    incident_id: str,
    context_minutes: int = Query(3, ge=1, le=30),
):
    service = get_service_diagnostics_service()
    try:
        return service.get_incident_detail(incident_id, context_minutes=context_minutes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Incident {incident_id} not found") from exc
