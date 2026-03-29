from fastapi import APIRouter

from app.services.alerts_engine import build_agency_alerts

router = APIRouter()


@router.get("/agency")
async def agency_alerts():
    alerts = await build_agency_alerts()
    return {
        "ok": True,
        "alerts": alerts,
    }
