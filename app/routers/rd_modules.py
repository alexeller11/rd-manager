from fastapi import APIRouter, HTTPException, Query

from app.services.rd_modules import (
    get_client_module_items,
    get_client_module_overview,
)

router = APIRouter()


@router.get("/client/{client_id}/overview")
async def module_overview(client_id: int):
    try:
        data = await get_client_module_overview(client_id)
        return {
            "ok": True,
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/client/{client_id}/{module_name}")
async def module_items(client_id: int, module_name: str, limit: int = Query(default=100)):
    try:
        data = await get_client_module_items(client_id, module_name, limit=limit)
        return {
            "ok": True,
            "data": data,
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
