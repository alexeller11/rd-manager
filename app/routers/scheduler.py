from fastapi import APIRouter, Depends
from app.auth_core import get_current_user
from app.database import db_fetchall

router = APIRouter()


@router.get("/status")
async def scheduler_status(user=Depends(get_current_user)):
    """Status do scheduler — informa que análises semanais são disparadas manualmente."""
    clients = await db_fetchall("SELECT id, name FROM clients")
    return {
        "status": "manual",
        "message": "Use POST /api/intel/weekly/run-all para disparar análises semanais.",
        "client_count": len(clients),
    }


@router.post("/run-weekly")
async def trigger_weekly_all(user=Depends(get_current_user)):
    """Atalho para disparar análise semanal de todos os clientes."""
    from fastapi import BackgroundTasks
    from app.routers.intelligence import run_weekly_analysis_job
    clients = await db_fetchall("SELECT id FROM clients")
    for c in clients:
        import asyncio
        asyncio.create_task(run_weekly_analysis_job(c["id"]))
    return {"message": f"Análise iniciada para {len(clients)} clientes."}
