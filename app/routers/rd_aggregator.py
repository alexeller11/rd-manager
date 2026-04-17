import asyncio
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.auth_core import get_valid_mkt_token

router = APIRouter()
logger = logging.getLogger(__name__)

RD_PLATFORM_BASE = "https://api.rd.services/platform"

# ── Helpers ────────────────────────────────────────────────────────────────────

def _safe_list(payload: Any) -> List[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("items", "data", "results", "segmentations", "landing_pages", "campaigns", "workflows", "contacts"):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


def _safe_preview(items: List[dict], limit: int = 5) -> List[dict]:
    return items[:limit]


def _to_iso_date(days_back: int = 30) -> str:
    dt = datetime.now(timezone.utc) - timedelta(days=days_back)
    return dt.strftime("%Y-%m-%d")


# ── fix #12: client compartilhado por request (connection pool) ────────────────
# Em vez de criar/destruir um AsyncClient em cada _rd_get,
# criamos UM client por bloco de chamadas e repassamos via argumento.
# Isso reutiliza conexões TCP para o mesmo host.

@asynccontextmanager
async def _rd_client(token: str):
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(
        base_url=RD_PLATFORM_BASE,
        headers=headers,
        timeout=30.0,
    ) as client:
        yield client


async def _rd_get(
    client: httpx.AsyncClient,
    path: str,
    params: Optional[dict] = None,
) -> dict:
    try:
        response = await client.get(path, params=params or {})
    except httpx.RequestError as exc:
        logger.error("RD API request error em %s: %s", path, exc)
        raise HTTPException(status_code=502, detail=f"Erro de conexão com RD API em {path}")

    if response.status_code >= 400:
        logger.warning("RD API %s em %s: %s", response.status_code, path, response.text[:300])
        raise HTTPException(
            status_code=response.status_code,
            detail=f"RD API error em {path}: {response.text[:300]}",
        )

    try:
        return response.json()
    except Exception:
        logger.error("Resposta inválida (não-JSON) da RD API em %s", path)
        raise HTTPException(status_code=500, detail=f"Resposta inválida da RD API em {path}")


# ── Wrappers de endpoint RD ────────────────────────────────────────────────────

async def _get_landing_pages(client, limit=50, page=1):
    return await _rd_get(client, "/landing_pages", {"page": page, "limit": limit})

async def _get_segmentations(client, limit=50, page=1):
    return await _rd_get(client, "/segmentations", {"page": page, "limit": limit})

async def _get_segment_contacts(client, segment_id: str, limit=100, page=1):
    return await _rd_get(client, f"/segmentations/{segment_id}/contacts", {"page": page, "limit": limit})

async def _get_workflows(client, limit=50, page=1):
    return await _rd_get(client, "/workflows", {"page": page, "limit": limit})

async def _get_workflow_detail(client, workflow_id: str):
    return await _rd_get(client, f"/workflows/{workflow_id}")

async def _get_campaigns(client, limit=50, page=1):
    return await _rd_get(client, "/campaigns", {"page": page, "limit": limit})

async def _get_campaign_items(client, campaign_id: str, limit=100, page=1):
    return await _rd_get(client, f"/campaigns/{campaign_id}/items", {"page": page, "limit": limit})

async def _get_email_metrics(client, start_date: str, end_date: str):
    return await _rd_get(client, "/analytics/emails", {"start_date": start_date, "end_date": end_date})


# ── fix #7: score qualitativo (não apenas quantidade) ─────────────────────────

def _compute_score(landing: dict, workflows: dict, segmentations: dict, campaigns: dict, metrics: dict) -> int:
    score = 0

    # Landing pages: até 20pts — premia pelo menos 1 ativa
    lp_count = landing.get("count", 0)
    if lp_count >= 3:
        score += 20
    elif lp_count >= 1:
        score += 10

    # Workflows: até 20pts — premia workflows ativos
    wf_items = workflows.get("items", [])
    wf_active = sum(1 for w in wf_items if str(w.get("status", "")).lower() in ("active", "enabled", "ativo"))
    if wf_active >= 3:
        score += 20
    elif wf_active >= 1:
        score += 12
    elif workflows.get("count", 0) >= 1:
        score += 5  # têm workflows mas nenhum ativo

    # Segmentações: até 20pts
    seg_count = segmentations.get("count", 0)
    if seg_count >= 5:
        score += 20
    elif seg_count >= 2:
        score += 12
    elif seg_count >= 1:
        score += 6

    # Campanhas: até 20pts — premia open_rate
    camp_count = campaigns.get("count", 0)
    if camp_count >= 1:
        score += 10
    raw_metrics = metrics.get("raw", {})
    open_rate = 0.0
    if isinstance(raw_metrics, dict):
        open_rate = float(raw_metrics.get("open_rate") or raw_metrics.get("avg_open_rate") or 0)
    if open_rate >= 25:
        score += 10
    elif open_rate >= 15:
        score += 5

    # Métricas disponíveis: até 20pts — penaliza erros de API
    if "error" not in landing and "error" not in campaigns:
        score += 20

    return min(score, 100)


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/overview/{client_id}")
async def rd_overview(
    client_id: int,
    days_back: int = Query(30, ge=1, le=365),
):
    token = await get_valid_mkt_token(client_id)
    start_date = _to_iso_date(days_back)
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    async with _rd_client(token) as client:
        results = await asyncio.gather(
            _get_landing_pages(client),
            _get_segmentations(client),
            _get_workflows(client),
            _get_campaigns(client),
            _get_email_metrics(client, start_date=start_date, end_date=end_date),
            return_exceptions=True,
        )

    landing_raw, segment_raw, workflow_raw, campaign_raw, metrics_raw = results

    def normalize(result: Any, ctx: str) -> dict:
        if isinstance(result, Exception):
            logger.warning("rd_overview: falha em %s para cliente %s: %s", ctx, client_id, result)
            return {"error": str(result), "items": [], "count": 0}
        items = _safe_list(result)
        return {"raw": result, "items": items, "count": len(items), "preview": _safe_preview(items)}

    landing      = normalize(landing_raw, "landing_pages")
    segmentations = normalize(segment_raw, "segmentations")
    workflows    = normalize(workflow_raw, "workflows")
    campaigns    = normalize(campaign_raw, "campaigns")

    if isinstance(metrics_raw, Exception):
        logger.warning("rd_overview: falha em metrics para cliente %s: %s", client_id, metrics_raw)
        metrics = {"error": str(metrics_raw)}
    else:
        metrics = {"raw": metrics_raw}

    score = _compute_score(landing, workflows, segmentations, campaigns, metrics)

    alerts = []
    if landing["count"] == 0:
        alerts.append("Nenhuma landing page encontrada.")
    if workflows["count"] == 0:
        alerts.append("Nenhum fluxo de automação encontrado.")
    if segmentations["count"] == 0:
        alerts.append("Nenhuma segmentação encontrada.")
    if campaigns["count"] == 0:
        alerts.append("Nenhuma campanha encontrada ou conta sem acesso ao módulo.")

    return {
        "client_id": client_id,
        "score": score,
        "alerts": alerts,
        "landing_pages": landing,
        "segmentations": segmentations,
        "workflows": workflows,
        "campaigns": campaigns,
        "metrics": metrics,
        "period": {"start_date": start_date, "end_date": end_date},
    }


@router.get("/landing-pages/{client_id}")
async def rd_landing_pages(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_landing_pages(client, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "count": len(items), "items": items, "raw": data}


@router.get("/segmentations/{client_id}")
async def rd_segmentations(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_segmentations(client, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "count": len(items), "items": items, "raw": data}


@router.get("/segmentations/{client_id}/{segment_id}/contacts")
async def rd_segment_contacts(
    client_id: int,
    segment_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_segment_contacts(client, segment_id=segment_id, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "segment_id": segment_id, "count": len(items), "items": items, "raw": data}


@router.get("/leads-base/{client_id}")
async def rd_leads_base(
    client_id: int,
    segment_limit: int = Query(5, ge=1, le=20),
    leads_per_segment: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)

    async with _rd_client(token) as client:
        seg_data = await _get_segmentations(client, page=1, limit=segment_limit)
        segments = _safe_list(seg_data)

        valid_segments = [
            seg for seg in segments
            if str(seg.get("id") or seg.get("uuid") or "")
        ]

        # fix #4: gather paralelo em vez de loop sequencial
        async def _fetch_segment(seg):
            segment_id = str(seg.get("id") or seg.get("uuid") or "")
            contacts_data = await _get_segment_contacts(client, segment_id=segment_id, page=1, limit=leads_per_segment)
            contacts = _safe_list(contacts_data)
            return {
                "segment": seg,
                "contacts_count": len(contacts),
                "contacts_preview": contacts[:10],
            }

        collected_segments = await asyncio.gather(
            *[_fetch_segment(seg) for seg in valid_segments],
            return_exceptions=True,
        )

    results = [r for r in collected_segments if not isinstance(r, Exception)]
    total_contacts = sum(r["contacts_count"] for r in results)

    return {
        "client_id": client_id,
        "segments_used": len(results),
        "estimated_contacts_loaded": total_contacts,
        "segments": results,
        "note": "Base agregada via segmentações em paralelo.",
    }


@router.get("/workflows/{client_id}")
async def rd_workflows(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_workflows(client, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "count": len(items), "items": items, "raw": data}


@router.get("/workflows/{client_id}/{workflow_id}")
async def rd_workflow_detail(client_id: int, workflow_id: str):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_workflow_detail(client, workflow_id=workflow_id)
    return {"client_id": client_id, "workflow_id": workflow_id, "data": data}


@router.get("/automations/{client_id}")
async def rd_automations(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    return await rd_workflows(client_id=client_id, page=page, limit=limit)


@router.get("/campaigns/{client_id}")
async def rd_campaigns(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_campaigns(client, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "count": len(items), "items": items, "raw": data}


@router.get("/campaigns/{client_id}/{campaign_id}/items")
async def rd_campaign_items(
    client_id: int,
    campaign_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    async with _rd_client(token) as client:
        data = await _get_campaign_items(client, campaign_id=campaign_id, page=page, limit=limit)
    items = _safe_list(data)
    return {"client_id": client_id, "campaign_id": campaign_id, "count": len(items), "items": items, "raw": data}


@router.get("/metrics/{client_id}")
async def rd_metrics(
    client_id: int,
    days_back: int = Query(30, ge=1, le=365),
):
    token = await get_valid_mkt_token(client_id)
    start_date = _to_iso_date(days_back)
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    async with _rd_client(token) as client:
        email_metrics = await _get_email_metrics(client, start_date=start_date, end_date=end_date)
    return {
        "client_id": client_id,
        "period": {"start_date": start_date, "end_date": end_date},
        "email_metrics": email_metrics,
    }
