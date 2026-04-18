"""RD Station CRM API v1 — Integração Centralizada."""
import json
import logging
import httpx
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchval, parse_json_field
from app.ai_service import call_ai, build_client_context, SYSTEM_STRATEGIST
from app.routers.clients import fetch_client

router = APIRouter()
logger = logging.getLogger(__name__)

RD_CRM = "https://crm.rdstation.com/api/v1"

_CRM_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def _get_crm_http_client() -> httpx.AsyncClient:
    global _CRM_HTTP_CLIENT
    if _CRM_HTTP_CLIENT is None or _CRM_HTTP_CLIENT.is_closed:
        _CRM_HTTP_CLIENT = httpx.AsyncClient(
            base_url=RD_CRM,
            timeout=httpx.Timeout(30.0, connect=5.0),
            follow_redirects=True,
            limits=httpx.Limits(
                max_keepalive_connections=10,
                max_connections=20,
                keepalive_expiry=30.0,
            ),
        )
    return _CRM_HTTP_CLIENT


async def crm_get(token: str, path: str, params: dict = None, limit: int = 200):
    """Auxiliar para chamadas GET à API do CRM."""
    headers = {"Accept": "application/json"}
    p = dict(params or {})
    p["token"] = token
    if limit:
        p["limit"] = limit

    logger.debug("CRM GET %s params=%s", path, list(p.keys()))

    try:
        client = _get_crm_http_client()
        r = await client.get(path, headers=headers, params=p)
        logger.debug("CRM GET %s → %s", path, r.status_code)
        if r.status_code == 200:
            return r.json(), 200
        return None, r.status_code
    except Exception as e:
        logger.exception("Erro CRM GET %s: %s", path, e)
        return None, 0


async def _get_crm_token(client_id: int) -> str | None:
    """Recupera o token CRM do banco de dados."""
    row = await db_fetchone("SELECT rd_crm_token FROM clients WHERE id=$1", client_id)
    return (row.get("rd_crm_token") or "").strip() or None if row else None


async def _get_crm_snapshot(client_id: int) -> dict:
    """Recupera o último snapshot do CRM salvo."""
    row = await db_fetchone(
        "SELECT data FROM crm_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    return parse_json_field(row["data"]) if row else {}


@router.get("/sync/{client_id}")
async def sync_crm(client_id: int):
    """Sincroniza os dados do CRM e salva um snapshot."""
    crm_token = await _get_crm_token(client_id)
    if not crm_token:
        raise HTTPException(400, "Token CRM não configurado no cadastro do cliente.")

    snap = {
        "total_deals": 0, "won_deals": 0, "lost_deals": 0,
        "total_revenue": 0.0, "recent_deals": [],
        "synced_at": datetime.now(timezone.utc).isoformat(), "errors": {}
    }

    raw, st = await crm_get(crm_token, "/deals", {"page": 1}, limit=100)
    if st == 200 and raw is not None:
        deals = []
        if isinstance(raw, dict):
            deals = raw.get("deals", [])
            snap["total_deals"] = raw.get("total", len(deals))
        elif isinstance(raw, list):
            deals = raw
            snap["total_deals"] = len(deals)

        for d in deals:
            val = d.get("amount") or d.get("value") or 0
            try:
                amt = float(val)
            except Exception:
                amt = 0.0

            status = str(d.get("status", "")).lower()
            if status == "won" or d.get("win") is True:
                snap["won_deals"] += 1
                snap["total_revenue"] += amt
            elif status == "lost" or d.get("win") is False:
                snap["lost_deals"] += 1

        snap["recent_deals"] = deals[:10]

        await db_fetchval(
            "INSERT INTO crm_snapshots (client_id, data) VALUES ($1,$2) RETURNING id",
            client_id, json.dumps(snap, ensure_ascii=False)
        )
        return {"success": True, "data": snap}
    else:
        raise HTTPException(st or 500, f"Erro ao acessar API RD CRM (Status {st})")


@router.post("/analyze")
async def analyze_crm(req: dict):
    """Usa IA para analisar o pipeline do CRM."""
    client_id = req.get("client_id")
    if not client_id:
        raise HTTPException(400, "ID do cliente é obrigatório")

    client_obj = await fetch_client(client_id)
    crm_data = await _get_crm_snapshot(client_id)

    if not crm_data:
        raise HTTPException(400, "Sincronize o CRM primeiro para gerar dados para a IA.")

    client_dict = dict(client_obj)
    client_dict["crm_data"] = crm_data
    context = build_client_context(client_dict)
    prompt = f"Analise o pipeline e performance de vendas deste cliente. Identifique gargalos e oportunidades.\n\n{context}"

    result = await call_ai(prompt, system=SYSTEM_STRATEGIST)
    return {"result": result}
