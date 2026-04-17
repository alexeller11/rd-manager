"""
Sincronização completa RD Station — por cliente ou todos de uma vez.
"""
from fastapi import APIRouter, HTTPException
from app.database import db_fetch_all, db_fetch_one

router = APIRouter()


async def _sync_single_client(client_id: int) -> dict:
    """Executa sync completo de um cliente. Reutilizável internamente."""
    try:
        from app.services.rd_sync import sync_client_full
        result = await sync_client_full(client_id)
        return {"client_id": client_id, "status": "ok", "detail": result}
    except Exception as e:
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
    Sincroniza todos os clientes com token RD ativo.
    Retorna resumo por cliente com status ok/error.
    """
    clients = await db_fetch_all(
        "SELECT id, name FROM clients ORDER BY name"
    )
    if not clients:
        return {"message": "Nenhum cliente cadastrado", "results": []}

    results = []
    ok_count = 0
    error_count = 0

    for client in clients:
        result = await _sync_single_client(client["id"])
        result["client_name"] = client["name"]
        results.append(result)
        if result["status"] == "ok":
            ok_count += 1
        else:
            error_count += 1

    return {
        "message": f"Sync concluído — {ok_count} ok, {error_count} com erro",
        "total": len(clients),
        "ok": ok_count,
        "errors": error_count,
        "results": results,
    }
