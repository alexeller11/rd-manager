"""RD Station CRM API v1 — Integração Centralizada."""
import json
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchval, parse_json_field
from app.ai_service import call_ai, build_client_context, SYSTEM_STRATEGIST
from app.routers.clients import fetch_client

router = APIRouter()
RD_CRM = "https://api.rd.services/crm/v1"

async def crm_get(token: str, path: str, params: dict = None, limit: int = 200):
    """Auxiliar para chamadas GET à API do CRM."""
    headers = {"Authorization": f"Token token={token}", "Accept": "application/json"}
    p = dict(params or {})
    p.setdefault("limit", limit)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{RD_CRM}{path}", headers=headers, params=p)
            if r.status_code == 200:
                return r.json(), 200
            return None, r.status_code
    except Exception as e:
        print(f"Erro CRM GET: {e}")
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
        "synced_at": datetime.now().isoformat(), "errors": {}
    }

    raw, st = await crm_get(crm_token, "/deals", {"page": 1}, limit=500)
    if st == 200 and raw:
        deals = raw.get("deals", []) if isinstance(raw, dict) else raw
        snap["total_deals"] = raw.get("total", len(deals)) if isinstance(raw, dict) else len(deals)
        for d in deals:
            amt = float(d.get("amount") or d.get("value") or 0)
            if d.get("win") or d.get("mark_as_won"):
                snap["won_deals"] += 1; snap["total_revenue"] += amt
            elif d.get("win") is False or d.get("mark_as_lost"):
                snap["lost_deals"] += 1
        snap["recent_deals"] = deals[:20]
        
        # Salva o snapshot no banco
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
    if not client_id: raise HTTPException(400, "ID do cliente é obrigatório")
    
    client_obj = await fetch_client(client_id)
    crm_data = await _get_crm_snapshot(client_id)
    
    if not crm_data:
        raise HTTPException(400, "Sincronize o CRM primeiro para gerar dados para a IA.")
        
    context = build_client_context({**client_obj, "crm_data": crm_data})
    prompt = f"Analise o pipeline e performance de vendas deste cliente. Identifique gargalos e oportunidades.\n\n{context}"
    
    result = await call_ai(prompt, system=SYSTEM_STRATEGIST)
    return {"result": result}
