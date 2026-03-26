from fastapi import APIRouter
from app.services.agency_intelligence import build_agency_overview

router = APIRouter()

@router.get("/overview")
async def agency_overview():
    return await build_agency_overview()
