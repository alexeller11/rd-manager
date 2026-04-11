from fastapi import APIRouter, HTTPException, Query

from app.services.seo_geo_audit import (
    audit_client_landing_pages,
    audit_client_website,
)

router = APIRouter()


@router.get("/client/{client_id}/website")
async def website_audit(client_id: int):
    try:
        data = await audit_client_website(client_id)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/landing-pages")
async def landing_pages_audit(client_id: int, limit: int = Query(default=10)):
    try:
        data = await audit_client_landing_pages(client_id, limit=limit)
        return {"ok": True, "data": data}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
