"""RD Station CRM API v1 — Integração Centralizada."""
import json
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchval, parse_json_field
from app.auth_core import get_valid_mkt_token, get_current_user
from app.ai_service import call_ai, build_client_context, SYSTEM_STRATEGIST, SYSTEM_EXPERT
from app.routers.clients import fetch_client

router = APIRouter()
RD_CRM = "https://crm.rdstation.com.br/api/v1"
RD_MKT = "https://api.rd.services"


async def crm_get(token: str, path: str, params: dict = None, limit: int = 200):
    p = dict(params or {})
    p["token"] = token
    p.setdefault("limit", limit)
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(f"{RD_CRM}{path}", params=p)
            return (r.json(), r.status_code) if r.status_code == 200 else (None, r.status_code)
    except Exception:
        return (None, 0)


async def mkt_get(token: str, path: str, params: dict = None):
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            r = await client.get(
                f"{RD_MKT}{path}",
                headers={"Authorization": f"Bearer {token}", "Accept": "application/json"},
                params=params or {}
            )
            return (r.json() if r.status_code == 200 else None, r.status_code)
    except Exception:
        return (None, 0)


async def _get_crm_token(client_id: int) -> str | None:
    row = await db_fetchone("SELECT rd_crm_token FROM clients WHERE id=$1", client_id)
    return (row.get("rd_crm_token") or "").strip() or None if row else None


async def _get_crm_snapshot(client_id: int) -> dict:
    row = await db_fetchone(
        "SELECT data FROM crm_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    return parse_json_field(row["data"]) if row else {}


def safe_list(val, *keys) -> list:
    if isinstance(val, list): return val
    if isinstance(val, dict):
        for k in keys:
            if k in val and isinstance(val[k], list): return val[k]
        for v in val.values():
            if isinstance(v, list): return v
    return []


@router.get("/sync/{client_id}")
async def sync_crm(client_id: int, user=Depends(get_current_user)):
    crm_token = await _get_crm_token(client_id)
    if not crm_token:
        return {"success": False, "errors": {"crm": "Token CRM não configurado."}}

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
        snap_json = json.dumps(snap, ensure_ascii=False)
        await db_fetchval(
            "INSERT INTO crm_snapshots (client_id, data) VALUES ($1,$2) RETURNING id",
            client_id, snap_json
        )
    else:
        snap["errors"]["deals"] = f"HTTP {st}"

    return {"success": True, "data": snap}


@router.get("/snapshot/{client_id}")
async def get_crm_snapshot(client_id: int, user=Depends(get_current_user)):
    snap = await _get_crm_snapshot(client_id)
    return {"data": snap}


@router.get("/landing-pages/{client_id}")
async def get_landing_pages(client_id: int, user=Depends(get_current_user)):
    mkt_token = await get_valid_mkt_token(client_id)
    if not mkt_token:
        return {"landing_pages": [], "total": 0}
    data, st = await mkt_get(mkt_token, "/platform/landing_pages", {"page": 1, "page_size": 50})
    lps = safe_list(data, "landing_pages", "items") if st == 200 else []
    return {"landing_pages": lps, "total": len(lps)}


@router.get("/sent-emails/{client_id}")
async def get_sent_emails(client_id: int, user=Depends(get_current_user)):
    mkt_token = await get_valid_mkt_token(client_id)
    if not mkt_token:
        return {"emails": [], "total": 0}
    data, st = await mkt_get(mkt_token, "/platform/emails", {"page": 1, "page_size": 50})
    emails = safe_list(data, "items", "emails") if st == 200 else []
    return {"emails": emails, "total": len(emails)}


@router.get("/channels/{client_id}")
async def get_channels(client_id: int, user=Depends(get_current_user)):
    mkt_token = await get_valid_mkt_token(client_id)
    if not mkt_token:
        return {"channels": []}
    data, st = await mkt_get(mkt_token, "/platform/contacts", {"page": 1, "page_size": 100})
    contacts = safe_list(data, "contacts", "items") if st == 200 else []
    sources = {}
    for c in contacts:
        src = c.get("traffic_source") or c.get("source") or "Desconhecido"
        sources[src] = sources.get(src, 0) + 1
    total = sum(sources.values()) or 1
    return {"channels": [
        {"source": k, "count": v, "percentage": round(v / total * 100, 1)}
        for k, v in sorted(sources.items(), key=lambda x: -x[1])
    ]}


class CRMAnalysisRequest(BaseModel):
    client_id: int
    type: str = "pipeline"
    extra: Optional[str] = None


@router.post("/analyze")
async def analyze_crm(req: CRMAnalysisRequest, user=Depends(get_current_user)):
    client_obj = await fetch_client(req.client_id)
    crm_data = await _get_crm_snapshot(req.client_id)
    context = build_client_context({**client_obj, "crm_data": crm_data})
    prompt = f"Analise o pipeline e performance de vendas. Identifique gargalos e oportunidades.\n\n{context}"
    result = await call_ai(prompt, system=SYSTEM_STRATEGIST)
    return {"result": result}


@router.post("/landing-pages/analyze")
async def analyze_crm_lps(req: CRMAnalysisRequest, user=Depends(get_current_user)):
    return await analyze_crm(req, user)


@router.post("/base/analyze")
async def analyze_base(req: CRMAnalysisRequest, user=Depends(get_current_user)):
    client_obj = await fetch_client(req.client_id)
    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    rd_snap = parse_json_field(snap_row["data"]) if snap_row else {}
    context = build_client_context({**client_obj, "rd_data": rd_snap})
    prompt = f"Analise a saúde da base de leads e engajamento de marketing.\n\n{context}"
    result = await call_ai(prompt, system=SYSTEM_EXPERT)
    return {"result": result}
