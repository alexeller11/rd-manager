"""
Integração RD Station Marketing com:
- retry
- refresh automático de token
- lock por cliente
- sync run auditável
"""
import asyncio
import json
from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai_service import (
    SYSTEM_EXPERT,
    SYSTEM_STRATEGIST,
    build_client_context,
    call_ai,
    call_ai_json,
)
from app.auth_core import get_valid_mkt_token, refresh_mkt_token
from app.database import db_execute, db_fetchone, db_fetchval, parse_json_field
from app.routers.clients import fetch_client

router = APIRouter()

RD_API = "https://api.rd.services"
SYNC_LOCKS: dict[int, asyncio.Lock] = {}


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_int(val, default=0) -> int:
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


def safe_list(val, *keys) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        for key in keys:
            if isinstance(val.get(key), list):
                return val[key]
        for item in val.values():
            if isinstance(item, list):
                return item
    return []


async def _log_error(client_id: int, endpoint: str, method: str, error_message: str) -> None:
    await db_execute(
        """
        INSERT INTO error_logs (client_id, endpoint, method, error_message, stack_trace)
        VALUES ($1, $2, $3, $4, $5)
        """,
        client_id,
        endpoint,
        method,
        error_message,
        "",
    )


async def _create_sync_run(client_id: int, sync_type: str) -> int:
    return await db_fetchval(
        """
        INSERT INTO sync_runs (client_id, sync_type, status, details, started_at)
        VALUES ($1, $2, $3, $4, $5)
        RETURNING id
        """,
        client_id,
        sync_type,
        "running",
        "",
        utcnow_iso(),
    )


async def _finish_sync_run(sync_run_id: int, status: str, details: dict | None = None) -> None:
    await db_execute(
        """
        UPDATE sync_runs
           SET status = $1,
               details = $2,
               finished_at = $3
         WHERE id = $4
        """,
        status,
        json.dumps(details or {}, ensure_ascii=False),
        utcnow_iso(),
        sync_run_id,
    )


async def rd_request(
    client_id: int,
    method: str,
    path: str,
    params: dict | None = None,
    retries: int = 3,
) -> dict:
    token = await get_valid_mkt_token(client_id)
    if not token:
        raise HTTPException(status_code=400, detail="Token RD Marketing não configurado")

    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        for attempt in range(retries):
            response = await client.request(method, f"{RD_API}{path}", headers=headers, params=params or {})

            if response.status_code == 200:
                return response.json()

            if response.status_code == 401:
                refreshed = await refresh_mkt_token(client_id)
                if not refreshed:
                    raise HTTPException(status_code=401, detail="Token RD expirado e refresh falhou")
                headers["Authorization"] = f"Bearer {refreshed}"
                continue

            if response.status_code in {429, 500, 502, 503, 504} and attempt < retries - 1:
                await asyncio.sleep(2 ** attempt)
                continue

            raise HTTPException(
                status_code=response.status_code,
                detail=f"RD Station error em {path}: {response.text[:300]}",
            )

    raise HTTPException(status_code=500, detail=f"Falha persistente ao acessar {path}")


async def save_rd_snapshot(client_id: int, snap: dict) -> None:
    await db_fetchval(
        """
        INSERT INTO rd_snapshots (client_id, data, snapshot_type)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        client_id,
        json.dumps(snap, ensure_ascii=False),
        "full_sync",
    )


async def get_rd_snapshot(client_id: int) -> dict:
    row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1",
        client_id,
    )
    if not row:
        return {}
    return parse_json_field(row["data"])


async def _fetch_segmentations(client_id: int) -> tuple[list[dict], int]:
    data = await rd_request(client_id, "GET", "/platform/segmentations", {"page": 1, "page_size": 100})
    segs_raw = safe_list(data, "segmentations", "items")
    segmentations = [
        {
            "id": str(s.get("id")),
            "name": s.get("name"),
            "contacts": safe_int(s.get("contacts_count") or s.get("contacts")),
        }
        for s in segs_raw
        if s.get("name")
    ]
    total_leads = max((s.get("contacts", 0) for s in segmentations), default=0)
    return segmentations, total_leads


async def _fetch_emails(client_id: int) -> tuple[list[dict], float, float]:
    data = await rd_request(client_id, "GET", "/platform/emails", {"page": 1, "page_size": 20})
    emails_raw = safe_list(data, "items", "emails")
    campaigns = []
    total_sent = 0
    total_open = 0
    total_click = 0

    for em in emails_raw:
        sent = max(safe_int(em.get("sends") or em.get("sent_count")), 1)
        opens = safe_int(em.get("opens") or em.get("open_count"))
        clicks = safe_int(em.get("clicks") or em.get("click_count"))
        total_sent += sent
        total_open += opens
        total_click += clicks

        campaigns.append(
            {
                "id": em.get("id"),
                "name": em.get("name") or "E-mail",
                "sent": sent,
                "opens": opens,
                "clicks": clicks,
                "open_rate": round(opens / sent * 100, 1),
                "click_rate": round(clicks / sent * 100, 1),
                "sent_at": em.get("sent_at") or em.get("created_at"),
            }
        )

    avg_open = round(total_open / total_sent * 100, 1) if total_sent else 0.0
    avg_click = round(total_click / total_sent * 100, 1) if total_sent else 0.0
    return campaigns, avg_open, avg_click


async def _fetch_workflows(client_id: int) -> list[dict]:
    data = await rd_request(client_id, "GET", "/platform/workflows", {"page": 1, "page_size": 50})
    workflows = safe_list(data, "workflows", "items")
    return [
        {
            "id": w.get("id"),
            "name": w.get("name"),
            "status": w.get("status"),
        }
        for w in workflows
    ]


async def _fetch_landing_pages(client_id: int) -> list[dict]:
    data = await rd_request(client_id, "GET", "/platform/landing_pages", {"page": 1, "page_size": 30})
    lps = safe_list(data, "landing_pages", "items")
    result = []
    for lp in lps:
        visitors = safe_int(lp.get("visitors_count") or lp.get("visits"))
        conversions = safe_int(lp.get("conversions_count") or lp.get("leads"))
        rate = round(conversions / max(visitors, 1) * 100, 1)
        result.append(
            {
                "id": lp.get("id"),
                "name": lp.get("name") or lp.get("title"),
                "visitors": visitors,
                "conversions": conversions,
                "conversion_rate": rate,
            }
        )
    return result


@router.get("/sync/{client_id}")
async def sync_client(client_id: int):
    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    if client_id not in SYNC_LOCKS:
        SYNC_LOCKS[client_id] = asyncio.Lock()

    async with SYNC_LOCKS[client_id]:
        sync_run_id = await _create_sync_run(client_id, "full_sync")
        try:
            segmentations_task = _fetch_segmentations(client_id)
            emails_task = _fetch_emails(client_id)
            workflows_task = _fetch_workflows(client_id)
            landing_pages_task = _fetch_landing_pages(client_id)

            (segmentations, total_leads), (campaigns, avg_open, avg_click), automations, landing_pages = await asyncio.gather(
                segmentations_task,
                emails_task,
                workflows_task,
                landing_pages_task,
            )

            snapshot = {
                "total_leads": total_leads,
                "segmentations": segmentations,
                "recent_campaigns": campaigns,
                "automations": automations,
                "landing_pages": landing_pages,
                "avg_open_rate": avg_open,
                "avg_click_rate": avg_click,
                "synced_at": utcnow_iso(),
            }

            await save_rd_snapshot(client_id, snapshot)
            await _finish_sync_run(sync_run_id, "success", {"snapshot_saved": True})

            return {
                "success": True,
                "client_id": client_id,
                "total_leads": total_leads,
                "segmentations": len(segmentations),
                "campaigns": len(campaigns),
                "automations": len(automations),
                "landing_pages": len(landing_pages),
            }

        except HTTPException as e:
            await _log_error(client_id, "/api/rd/sync", "GET", str(e.detail))
            await _finish_sync_run(sync_run_id, "failed", {"error": str(e.detail)})
            raise
        except Exception as e:
            await _log_error(client_id, "/api/rd/sync", "GET", str(e))
            await _finish_sync_run(sync_run_id, "failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"Erro interno de sincronização: {e}")


@router.get("/diagnose/{client_id}")
async def diagnose_token(client_id: int):
    endpoints = [
        ("segmentations", "/platform/segmentations"),
        ("emails", "/platform/emails"),
        ("landing_pages", "/platform/landing_pages"),
        ("workflows", "/platform/workflows"),
    ]
    results = []
    for label, path in endpoints:
        try:
            await rd_request(client_id, "GET", path, {"page": 1, "page_size": 1})
            results.append({"name": label, "ok": True})
        except HTTPException as e:
            results.append({"name": label, "ok": False, "status": e.status_code, "detail": e.detail})
    return results


@router.get("/snapshot/{client_id}")
async def latest_snapshot(client_id: int):
    snapshot = await get_rd_snapshot(client_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Nenhum snapshot encontrado")
    return snapshot


@router.get("/leads-analysis/{client_id}")
async def get_leads_analysis(client_id: int, page: int = 1, page_size: int = 50, seg_id: str = ""):
    path = f"/platform/segmentations/{seg_id}/contacts" if seg_id else "/platform/contacts"
    try:
        data = await rd_request(client_id, "GET", path, {"page": page, "page_size": page_size})
    except HTTPException:
        if seg_id:
            data = await rd_request(client_id, "GET", "/platform/contacts", {"page": page, "page_size": page_size})
        else:
            raise

    contacts_raw = safe_list(data, "contacts", "items")
    leads = []
    for contact in contacts_raw:
        conversions = safe_int(contact.get("conversions") or contact.get("conversion_count"))
        score = min(conversions * 15, 100)
        potential = "alto" if score >= 70 else "medio" if score >= 30 else "baixo"
        leads.append(
            {
                "uuid": contact.get("uuid"),
                "name": contact.get("name") or (contact.get("email", "Lead").split("@")[0]),
                "email": contact.get("email"),
                "score": score,
                "potential": potential,
                "conversions": conversions,
                "last_activity": contact.get("last_conversion_date") or contact.get("updated_at"),
            }
        )

    return {"leads": leads, "total": safe_int(data.get("total", len(leads)))}


class AnalysisRequest(BaseModel):
    client_id: int
    type: Optional[str] = "general"


@router.post("/analyze")
async def analyze_marketing(req: AnalysisRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    client["rd_data"] = await get_rd_snapshot(req.client_id)
    context = build_client_context(client)

    result = await call_ai(
        prompt=f"""
Analise o desempenho de marketing da empresa abaixo.

{context}

Entregue:
1. diagnóstico executivo
2. 3 gargalos prioritários
3. 3 ações de alto impacto
4. 3 riscos de curto prazo
""",
        system=SYSTEM_EXPERT,
        max_tokens=2200,
        temperature=0.3,
    )
    return {"result": result}


@router.post("/flows/generate")
async def generate_flow(req: dict):
    client_id = req.get("client_id")
    objective = req.get("objective")
    flow_type = req.get("flow_type")

    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    context = build_client_context(client)

    schema = """
{
  "name": "Nome do fluxo",
  "description": "Resumo da estratégia",
  "nodes": [
    {
      "id": 1,
      "label": "Gatilho inicial",
      "type": "trigger"
    }
  ]
}
"""

    result = await call_ai_json(
        prompt=f"""
Crie um fluxo de automação estratégico.

Objetivo: {objective}
Tipo: {flow_type}

Contexto do cliente:
{context}

Regras:
- incluir gatilho
- incluir ações
- incluir condições
- incluir caminhos alternativos
- ser executável no contexto de automação de marketing
""",
        system=SYSTEM_STRATEGIST,
        schema_description=schema,
        max_tokens=1800,
    )
    return result
