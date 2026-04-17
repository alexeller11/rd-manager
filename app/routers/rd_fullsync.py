"""
Sincronização completa RD Station — por cliente ou todos de uma vez.
"""
import asyncio
import logging

from fastapi import APIRouter, HTTPException

from app.database import db_fetch_all, db_fetch_one

logger = logging.getLogger(__name__)
router = APIRouter()

# Limita concorrência no sync-all para não sobrecarregar a RD API nem o event loop
_SYNC_SEMAPHORE = asyncio.Semaphore(3)


async def _sync_single_client(client_id: int) -> dict:
    """Executa sync completo de um cliente. Reutilizável internamente."""
    async with _SYNC_SEMAPHORE:
        try:
            from app.services.rd_sync import sync_client_full
            result = await sync_client_full(client_id)
            return {"client_id": client_id, "status": "ok", "detail": result}
        except Exception as e:
            logger.error("Erro ao sincronizar cliente %s: %s", client_id, e)
            return {"client_id": client_id, "status": "error", "detail": str(e)}


@router.post("/run/{client_id}")
async def run_sync(client_id: int):
    """Sincroniza um cliente específico."""
    row = await db_fetch_one("SELECT id, name FROM clients WHERE id = $1", client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    result = await _sync_single_client(client_id)
    return {
        "message": f"Sync concluído para {row['name']}",
        "result": result,
    }


@router.post("/run-all")
async def run_sync_all():
    """
    Sincroniza todos os clientes com token RD ativo em paralelo (máx 3 simultâneos).
    Retorna resumo por cliente com status ok/error.
    """
    clients = await db_fetch_all(
        "SELECT id, name FROM clients ORDER BY name"
    )
    if not clients:
        return {"message": "Nenhum cliente cadastrado", "results": []}

    # Executa em paralelo com semáforo — não bloqueia o event loop
    tasks = [_sync_single_client(c["id"]) for c in clients]
    raw_results = await asyncio.gather(*tasks, return_exceptions=True)

    name_map = {c["id"]: c["name"] for c in clients}
    results = []
    ok_count = 0
    error_count = 0

    for client, res in zip(clients, raw_results):
        if isinstance(res, Exception):
            res = {"client_id": client["id"], "status": "error", "detail": str(res)}
        res["client_name"] = name_map.get(client["id"], "")
        results.append(res)
        if res.get("status") == "ok":
            ok_count += 1
        else:
            error_count += 1

    logger.info("Sync-all concluído: %s ok, %s erro", ok_count, error_count)
    return {
        "message": f"Sync concluído — {ok_count} ok, {error_count} com erro",
        "total": len(clients),
        "ok": ok_count,
        "errors": error_count,
        "results": results,
    }
