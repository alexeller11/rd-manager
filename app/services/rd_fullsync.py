import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from app.auth_core import get_valid_mkt_token
from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval

RD_PLATFORM_BASE = "https://api.rd.services/platform"


def _now():
    return datetime.now(timezone.utc)


def _safe_list(payload: Any) -> List[dict]:
    if payload is None:
        return []
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in (
            "items",
            "data",
            "results",
            "landing_pages",
            "segmentations",
            "campaigns",
            "workflows",
            "contacts",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return [payload]
    return []


async def ensure_sync_tables():
    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_runs (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TIMESTAMPTZ NOT NULL,
            finished_at TIMESTAMPTZ,
            summary JSONB,
            error TEXT
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_snapshots (
            id SERIAL PRIMARY KEY,
            client_id INTEGER NOT NULL,
            object_type TEXT NOT NULL,
            object_key TEXT NOT NULL,
            payload JSONB NOT NULL,
            synced_at TIMESTAMPTZ NOT NULL,
            UNIQUE (client_id, object_type, object_key)
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_summaries (
            client_id INTEGER PRIMARY KEY,
            summary JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL
        )
        """
    )


async def _rd_get(token: str, path: str, params: Optional[dict] = None) -> dict:
    url = f"{RD_PLATFORM_BASE}{path}"

    async with httpx.AsyncClient(timeout=40.0) as client:
        response = await client.get(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            params=params or {},
        )

    if response.status_code >= 400:
        raise Exception(f"RD API error em {path}: {response.status_code} | {response.text[:500]}")

    try:
        return response.json()
    except Exception:
        raise Exception(f"Resposta inválida da RD API em {path}")


async def _fetch_paginated(token: str, path: str, limit: int = 100, max_pages: int = 5) -> List[dict]:
    all_items: List[dict] = []

    for page in range(1, max_pages + 1):
        payload = await _rd_get(
            token,
            path,
            params={"page": page, "limit": limit},
        )
        items = _safe_list(payload)
        if not items:
            break
        all_items.extend(items)
        if len(items) < limit:
            break

    return all_items


async def _fetch_segment_contacts(token: str, segment_id: str, limit: int = 100, max_pages: int = 2) -> List[dict]:
    all_items: List[dict] = []

    for page in range(1, max_pages + 1):
        payload = await _rd_get(
            token,
            f"/segmentations/{segment_id}/contacts",
            params={"page": page, "limit": limit},
        )
        items = _safe_list(payload)
        if not items:
            break
        all_items.extend(items)
        if len(items) < limit:
            break

    return all_items


async def _fetch_email_metrics(token: str, days_back: int = 30) -> dict:
    end_date = _now().strftime("%Y-%m-%d")
    start_date = (_now()).replace(microsecond=0)
    start_date = (start_date).strftime("%Y-%m-%d")

    return await _rd_get(
        token,
        "/analytics/emails",
        params={
            "start_date": start_date,
            "end_date": end_date,
        },
    )


def _pick_object_key(item: dict, fallback_prefix: str, index: int) -> str:
    for key in ("id", "uuid", "identifier", "slug", "name", "title", "email"):
        value = item.get(key)
        if value is not None and str(value).strip() != "":
            return str(value)
    return f"{fallback_prefix}_{index}"


async def _upsert_snapshot(client_id: int, object_type: str, object_key: str, payload: dict):
    await db_execute(
        """
        INSERT INTO rd_sync_snapshots (
            client_id,
            object_type,
            object_key,
            payload,
            synced_at
        )
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (client_id, object_type, object_key)
        DO UPDATE SET
            payload = EXCLUDED.payload,
            synced_at = EXCLUDED.synced_at
        """,
        client_id,
        object_type,
        object_key,
        payload,
        _now(),
    )


async def _save_summary(client_id: int, summary: dict):
    await db_execute(
        """
        INSERT INTO rd_sync_summaries (client_id, summary, updated_at)
        VALUES ($1, $2, $3)
        ON CONFLICT (client_id)
        DO UPDATE SET
            summary = EXCLUDED.summary,
            updated_at = EXCLUDED.updated_at
        """,
        client_id,
        summary,
        _now(),
    )


async def _create_sync_run(client_id: int) -> int:
    run_id = await db_fetchval(
        """
        INSERT INTO rd_sync_runs (client_id, status, started_at)
        VALUES ($1, $2, $3)
        RETURNING id
        """,
        client_id,
        "running",
        _now(),
    )
    return int(run_id)


async def _finish_sync_run(run_id: int, status: str, summary: Optional[dict] = None, error: Optional[str] = None):
    await db_execute(
        """
        UPDATE rd_sync_runs
        SET
            status = $2,
            finished_at = $3,
            summary = $4,
            error = $5
        WHERE id = $1
        """,
        run_id,
        status,
        _now(),
        summary,
        error,
    )


async def run_full_sync(client_id: int) -> dict:
    await ensure_sync_tables()

    run_id = await _create_sync_run(client_id)

    try:
        token = await get_valid_mkt_token(client_id)

        landing_pages: List[dict] = []
        segmentations: List[dict] = []
        workflows: List[dict] = []
        campaigns: List[dict] = []
        metrics: dict = {}
        segment_contacts_summary: List[dict] = []
        module_errors: Dict[str, str] = {}

        # landing pages
        try:
            landing_pages = await _fetch_paginated(token, "/landing_pages", limit=100, max_pages=5)
            for idx, item in enumerate(landing_pages):
                await _upsert_snapshot(client_id, "landing_page", _pick_object_key(item, "landing_page", idx), item)
        except Exception as e:
            module_errors["landing_pages"] = str(e)

        # segmentations
        try:
            segmentations = await _fetch_paginated(token, "/segmentations", limit=100, max_pages=5)
            for idx, item in enumerate(segmentations):
                await _upsert_snapshot(client_id, "segmentation", _pick_object_key(item, "segmentation", idx), item)
        except Exception as e:
            module_errors["segmentations"] = str(e)

        # segment contacts preview / base aggregation
        try:
            for seg_idx, seg in enumerate(segmentations[:10]):
                segment_id = str(seg.get("id") or seg.get("uuid") or "").strip()
                if not segment_id:
                    continue

                contacts = await _fetch_segment_contacts(token, segment_id=segment_id, limit=100, max_pages=2)
                segment_contacts_summary.append({
                    "segment": seg,
                    "contacts_count": len(contacts),
                    "contacts_preview": contacts[:20],
                })

                await _upsert_snapshot(
                    client_id,
                    "segmentation_contacts",
                    segment_id,
                    {
                        "segment": seg,
                        "contacts_count": len(contacts),
                        "contacts_preview": contacts[:50],
                    },
                )
        except Exception as e:
            module_errors["leads_base"] = str(e)

        # workflows / automations
        try:
            workflows = await _fetch_paginated(token, "/workflows", limit=100, max_pages=5)
            for idx, item in enumerate(workflows):
                await _upsert_snapshot(client_id, "workflow", _pick_object_key(item, "workflow", idx), item)
        except Exception as e:
            module_errors["workflows"] = str(e)

        # campaigns
        try:
            campaigns = await _fetch_paginated(token, "/campaigns", limit=100, max_pages=5)
            for idx, item in enumerate(campaigns):
                await _upsert_snapshot(client_id, "campaign", _pick_object_key(item, "campaign", idx), item)
        except Exception as e:
            module_errors["campaigns"] = str(e)

        # metrics
        try:
            metrics = await _fetch_email_metrics(token, days_back=30)
            await _upsert_snapshot(client_id, "metrics", "email_metrics", metrics)
        except Exception as e:
            module_errors["metrics"] = str(e)

        summary = {
            "client_id": client_id,
            "synced_at": _now().isoformat(),
            "counts": {
                "landing_pages": len(landing_pages),
                "segmentations": len(segmentations),
                "segment_contact_groups": len(segment_contacts_summary),
                "workflows": len(workflows),
                "campaigns": len(campaigns),
            },
            "module_errors": module_errors,
            "segment_contacts_summary": segment_contacts_summary[:10],
            "metrics": metrics,
        }

        await _save_summary(client_id, summary)
        await _finish_sync_run(run_id, "success", summary=summary)

        return {
            "ok": True,
            "run_id": run_id,
            "summary": summary,
        }

    except Exception as e:
        await _finish_sync_run(run_id, "error", summary=None, error=str(e))
        return {
            "ok": False,
            "run_id": run_id,
            "error": str(e),
        }


async def get_last_summary(client_id: int):
    await ensure_sync_tables()

    row = await db_fetch_one(
        """
        SELECT client_id, summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )
    return row


async def get_last_run(client_id: int):
    await ensure_sync_tables()

    row = await db_fetch_one(
        """
        SELECT *
        FROM rd_sync_runs
        WHERE client_id = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        client_id,
    )
    return row


async def list_snapshots(client_id: int, object_type: Optional[str] = None):
    await ensure_sync_tables()

    if object_type:
        return await db_fetch_all(
            """
            SELECT id, client_id, object_type, object_key, payload, synced_at
            FROM rd_sync_snapshots
            WHERE client_id = $1 AND object_type = $2
            ORDER BY synced_at DESC
            """,
            client_id,
            object_type,
        )

    return await db_fetch_all(
        """
        SELECT id, client_id, object_type, object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1
        ORDER BY synced_at DESC
        """,
        client_id,
    )
