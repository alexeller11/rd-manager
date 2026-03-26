import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, HTTPException, Query

from app.auth_core import get_valid_mkt_token

router = APIRouter()

RD_PLATFORM_BASE = "https://api.rd.services/platform"


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


async def _rd_get(
    token: str,
    path: str,
    params: Optional[dict] = None,
) -> dict:
    url = f"{RD_PLATFORM_BASE}{path}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params or {},
        )

    if response.status_code >= 400:
        raise HTTPException(
            status_code=response.status_code,
            detail=f"RD API error em {path}: {response.text[:500]}",
        )

    try:
        return response.json()
    except Exception:
        raise HTTPException(
            status_code=500,
            detail=f"Resposta inválida da RD API em {path}",
        )


async def _get_landing_pages(token: str, limit: int = 50, page: int = 1) -> dict:
    return await _rd_get(
        token,
        "/landing_pages",
        params={"page": page, "limit": limit},
    )


async def _get_segmentations(token: str, limit: int = 50, page: int = 1) -> dict:
    return await _rd_get(
        token,
        "/segmentations",
        params={"page": page, "limit": limit},
    )


async def _get_segment_contacts(token: str, segment_id: str, limit: int = 100, page: int = 1) -> dict:
    return await _rd_get(
        token,
        f"/segmentations/{segment_id}/contacts",
        params={"page": page, "limit": limit},
    )


async def _get_workflows(token: str, limit: int = 50, page: int = 1) -> dict:
    return await _rd_get(
        token,
        "/workflows",
        params={"page": page, "limit": limit},
    )


async def _get_workflow_detail(token: str, workflow_id: str) -> dict:
    return await _rd_get(
        token,
        f"/workflows/{workflow_id}",
    )


async def _get_campaigns(token: str, limit: int = 50, page: int = 1) -> dict:
    return await _rd_get(
        token,
        "/campaigns",
        params={"page": page, "limit": limit},
    )


async def _get_campaign_items(token: str, campaign_id: str, limit: int = 100, page: int = 1) -> dict:
    return await _rd_get(
        token,
        f"/campaigns/{campaign_id}/items",
        params={"page": page, "limit": limit},
    )


async def _get_email_metrics(token: str, start_date: str, end_date: str) -> dict:
    return await _rd_get(
        token,
        "/analytics/emails",
        params={
            "start_date": start_date,
            "end_date": end_date,
        },
    )


@router.get("/overview/{client_id}")
async def rd_overview(
    client_id: int,
    days_back: int = Query(30, ge=1, le=365),
):
    token = await get_valid_mkt_token(client_id)
    start_date = _to_iso_date(days_back)
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    results = await asyncio.gather(
        _get_landing_pages(token),
        _get_segmentations(token),
        _get_workflows(token),
        _get_campaigns(token),
        _get_email_metrics(token, start_date=start_date, end_date=end_date),
        return_exceptions=True,
    )

    landing_raw, segment_raw, workflow_raw, campaign_raw, metrics_raw = results

    def normalize_result(result: Any) -> dict:
        if isinstance(result, Exception):
            return {"error": str(result), "items": [], "count": 0}
        items = _safe_list(result)
        return {
            "raw": result,
            "items": items,
            "count": len(items),
            "preview": _safe_preview(items),
        }

    landing = normalize_result(landing_raw)
    segmentations = normalize_result(segment_raw)
    workflows = normalize_result(workflow_raw)
    campaigns = normalize_result(campaign_raw)

    metrics = {"raw": metrics_raw} if not isinstance(metrics_raw, Exception) else {"error": str(metrics_raw)}

    score = 50
    score += min(10, landing["count"])
    score += min(10, workflows["count"])
    score += min(10, segmentations["count"])
    score += min(10, campaigns["count"])

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
        "score": min(score, 100),
        "alerts": alerts,
        "landing_pages": landing,
        "segmentations": segmentations,
        "workflows": workflows,
        "campaigns": campaigns,
        "metrics": metrics,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
    }


@router.get("/landing-pages/{client_id}")
async def rd_landing_pages(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_landing_pages(token, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/segmentations/{client_id}")
async def rd_segmentations(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_segmentations(token, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/segmentations/{client_id}/{segment_id}/contacts")
async def rd_segment_contacts(
    client_id: int,
    segment_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_segment_contacts(token, segment_id=segment_id, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "segment_id": segment_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/leads-base/{client_id}")
async def rd_leads_base(
    client_id: int,
    segment_limit: int = Query(5, ge=1, le=20),
    leads_per_segment: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    seg_data = await _get_segmentations(token, page=1, limit=segment_limit)
    segments = _safe_list(seg_data)

    collected_segments = []
    total_contacts = 0

    for seg in segments:
        segment_id = str(seg.get("id") or seg.get("uuid") or "")
        if not segment_id:
            continue

        contacts_data = await _get_segment_contacts(
            token,
            segment_id=segment_id,
            page=1,
            limit=leads_per_segment,
        )
        contacts = _safe_list(contacts_data)
        total_contacts += len(contacts)

        collected_segments.append({
            "segment": seg,
            "contacts_count": len(contacts),
            "contacts_preview": contacts[:10],
        })

    return {
        "client_id": client_id,
        "segments_used": len(collected_segments),
        "estimated_contacts_loaded": total_contacts,
        "segments": collected_segments,
        "note": "A base foi agregada a partir das segmentações e dos contatos por segmentação.",
    }


@router.get("/workflows/{client_id}")
async def rd_workflows(
    client_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_workflows(token, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/workflows/{client_id}/{workflow_id}")
async def rd_workflow_detail(
    client_id: int,
    workflow_id: str,
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_workflow_detail(token, workflow_id=workflow_id)

    return {
        "client_id": client_id,
        "workflow_id": workflow_id,
        "data": data,
    }


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
    data = await _get_campaigns(token, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/campaigns/{client_id}/{campaign_id}/items")
async def rd_campaign_items(
    client_id: int,
    campaign_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=200),
):
    token = await get_valid_mkt_token(client_id)
    data = await _get_campaign_items(token, campaign_id=campaign_id, page=page, limit=limit)
    items = _safe_list(data)

    return {
        "client_id": client_id,
        "campaign_id": campaign_id,
        "count": len(items),
        "items": items,
        "raw": data,
    }


@router.get("/metrics/{client_id}")
async def rd_metrics(
    client_id: int,
    days_back: int = Query(30, ge=1, le=365),
):
    token = await get_valid_mkt_token(client_id)
    start_date = _to_iso_date(days_back)
    end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    email_metrics = await _get_email_metrics(
        token,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "client_id": client_id,
        "period": {
            "start_date": start_date,
            "end_date": end_date,
        },
        "email_metrics": email_metrics,
    }
