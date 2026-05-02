from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/widgets", tags=["widgets"])


@router.get("/dothebay-lgbtq")
async def get_dothebay_lgbtq_widget_data():
    try:
        from services.widgets.dothebay_lgbtq import getDoTheBayWidgetData

        payload = getDoTheBayWidgetData()
        if payload.get("events") or payload.get("fetchedAt"):
            return payload
        raise HTTPException(status_code=502, detail=payload.get("error") or "Unable to load DoTheBay LGBTQ events")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))
