from fastapi import APIRouter, HTTPException

from app.services.rd_diagnostics import build_rd_diagnostics

router = APIRouter()


@router.get("/client/{client_id}")
async def rd_diagnostics(client_id: int):
    try:
        data = await build_rd_diagnostics(client_id)
        return {
            "ok": True,
            "diagnostics": data,
        }
    except Exception as e:
        raise HTTPException(status_code=404, detail=str(e))
