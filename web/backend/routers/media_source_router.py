from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from web.backend.database.database import get_db
from web.backend.services.desktophut_service import DesktopHutService


router = APIRouter(prefix="/api/media-sources", tags=["media-sources"])


@router.get("")
def list_media_sources(db: Session = Depends(get_db)):
    return DesktopHutService(db).list_sources()


@router.get("/desktophut/status")
def get_desktophut_status(db: Session = Depends(get_db)):
    return DesktopHutService(db).get_status()


@router.post("/desktophut/refresh")
def refresh_desktophut_cache(
    max_pages: int = Query(25, ge=1, le=250),
    force: bool = Query(False),
    db: Session = Depends(get_db),
):
    return DesktopHutService(db).refresh_cache(max_pages=max_pages, force=force)


@router.get("/desktophut/entries")
def browse_desktophut_entries(
    q: str = Query("", alias="query"),
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    return DesktopHutService(db).browse_entries(query=q, offset=offset, limit=limit)


@router.post("/desktophut/entries/{entry_id}/import")
def import_desktophut_entry(entry_id: int, db: Session = Depends(get_db)):
    try:
        return DesktopHutService(db).import_entry(entry_id)
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
