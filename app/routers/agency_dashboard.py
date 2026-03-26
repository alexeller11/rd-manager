import asyncio
from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException

from app.auth_core import get_current_user
from app.database import db_fetch_all
from app.services.scoring import build_agency_score, build_client_score
from app.routers.rd_aggregator import rd_overview

router = APIRouter()


async def _load_clients() -> List[dict]:
    """
    Busca clientes de forma tolerante a diferenças de schema.
    """
    queries = [
        """
        SELECT id, name, segment, website, description, rd_token, rd_refresh_token
        FROM clients
        ORDER BY id DESC
        """,
        """
        SELECT id, name, segment, website, description
        FROM clients
        ORDER BY id DESC
        """,
        """
        SELECT *
        FROM clients
        ORDER BY id DESC
        """,
    ]

    last_error = None
    for query in queries:
        try:
            rows = await db_fetch_all(query)
            return rows or []
        except Exception as e:
            last_error = e

    raise HTTPException(status_code=500, detail=f"Erro ao carregar clientes: {last_error}")


async def _build_client_dashboard_item(client: dict) -> dict:
    """
    Monta score do cliente e tenta agregar visão RD.
    """
    overview = {}
    try:
        overview = await rd_overview(client_id=int(client["id"]), days_back=30)
    except Exception as e:
        overview = {
            "error": str(e),
            "landing_pages": {"count": 0, "items": []},
            "segmentations": {"count": 0, "items": []},
            "workflows": {"count": 0, "items": []},
            "campaigns": {"count": 0, "items": []},
            "metrics": {},
        }

    normalized_client = {
        **client,
        "rd_connected": bool(client.get("rd_token") or client.get("rd_refresh_token")),
        "rd_token_set": bool(client.get("rd_token") or client.get("rd_refresh_token")),
    }

    score_data = build_client_score(normalized_client, overview)

    return {
        "client": normalized_client,
        "overview": overview,
        "score_data": score_data,
    }


@router.get("/overview", dependencies=[Depends(get_current_user)])
async def agency_overview():
    clients = await _load_clients()

    if not clients:
        return {
            "agency": build_agency_score([]),
            "clients": [],
        }

    rows = await asyncio.gather(
        *[_build_client_dashboard_item(client) for client in clients],
        return_exceptions=True,
    )

    client_rows = []
    for row in rows:
        if isinstance(row, Exception):
            continue
        client_rows.append(row)

    agency = build_agency_score([row["score_data"] for row in client_rows])

    return {
        "agency": agency,
        "clients": client_rows,
    }


@router.get("/client/{client_id}", dependencies=[Depends(get_current_user)])
async def agency_client_detail(client_id: int):
    clients = await _load_clients()
    client = next((c for c in clients if int(c["id"]) == int(client_id)), None)

    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    row = await _build_client_dashboard_item(client)
    return row
