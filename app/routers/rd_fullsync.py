from fastapi import APIRouter

from app.services.rd_fullsync import run_full_sync

router = APIRouter()


@router.post("/run/{client_id}")
async def run_sync(client_id: int):
    result = await run_full_sync(client_id)
    return result


@router.get("/summary/{client_id}")
async def get_summary(client_id: int):
    return {"message": "Use o dashboard para visualizar"}
