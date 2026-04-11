from fastapi import APIRouter, HTTPException, Query

from app.services.agency_expert import (
    build_automation_plan,
    build_reengagement_plan,
    get_base_segments,
    get_inactive_leads,
)

router = APIRouter()


@router.get("/client/{client_id}/inactive-leads")
async def inactive_leads(client_id: int, days: int = Query(default=60)):
    try:
        data = await get_inactive_leads(client_id, min_days=days)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/base-segments")
async def base_segments(client_id: int):
    try:
        data = await get_base_segments(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/automation-plan")
async def automation_plan(client_id: int):
    try:
        data = await build_automation_plan(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/reengagement-plan")
async def reengagement_plan(client_id: int, days: int = Query(default=60)):
    try:
        data = await build_reengagement_plan(client_id, min_days=days)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
