from fastapi import APIRouter

from app.services.prospecting import build_prospect_diagnosis

router = APIRouter()


@router.post("/analyze-business")
async def analyze_business(payload: dict):
    diagnosis = build_prospect_diagnosis(payload)
    return {
        "ok": True,
        "analysis": diagnosis,
    }
