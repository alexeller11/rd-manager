from fastapi import APIRouter, Query

from app.services.rd_fullsync import (
    get_last_run,
    get_last_summary,
    list_snapshots,
    run_full_sync,
)

router = APIRouter()


@router.post("/run/{client_id}")
async def run_sync(client_id: int):
    return await run_full_sync(client_id)


@router.get("/summary/{client_id}")
async def sync_summary(client_id: int):
    row = await get_last_summary(client_id)
    return {
        "ok": True,
        "data": row,
    }


@router.get("/last-run/{client_id}")
async def last_run(client_id: int):
    row = await get_last_run(client_id)
    return {
        "ok": True,
        "data": row,
    }


@router.get("/snapshots/{client_id}")
async def snapshots(client_id: int, object_type: str | None = Query(default=None)):
    rows = await list_snapshots(client_id, object_type=object_type)
    return {
        "ok": True,
        "count": len(rows or []),
        "items": rows or [],
    }
