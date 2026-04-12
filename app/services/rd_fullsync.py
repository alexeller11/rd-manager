import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import httpx

from app.auth_core import get_valid_mkt_token
from app.database import (
    db_execute,
    db_fetch_all,
    db_fetch_one,
    db_fetchval,
    using_postgres,
)

RD_PLATFORM_BASE = "https://api.rd.services/platform"


def _now():
    return datetime.now(timezone.utc)


def _json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return [_json_safe(v) for v in value]
    if isinstance(value, datetime):
        return value.isoformat()
    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def _jsonb(value: Any) -> str:
    return json.dumps(_json_safe(value), ensure_ascii=False)


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
            "emails",
        ):
            value = payload.get(key)
            if isinstance(value, list):
                return value
        return []
    return []


async def ensure_sync_tables():
    if using_postgres():
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
        return

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            status TEXT NOT NULL,
            started_at TEXT NOT NULL,
            finished_at TEXT,
            summary TEXT,
            error TEXT
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER NOT NULL,
            object_type TEXT NOT NULL,
            object_key TEXT NOT NULL,
            payload TEXT NOT NULL,
            synced_at TEXT NOT NULL,
            UNIQUE (client_id, object_type, object_key)
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_summaries (
            client_id INTEGER PRIMARY KEY,
            summary TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )


async def _rd_get_debug(
    client: httpx.AsyncClient, token: str, path: str, params: Optional[dict] = None
) -> dict:
    response = await client.get(
        f"{RD_PLATFORM_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        params=params or {},
    )

    text_preview = response.text[:800]

    payload = {}
    try:
        payload = response.json()
    except Exception:
        payload = {"raw_text": text_preview}

    return {
        "ok": response.status_code < 400,
        "status_code": response.status_code,
        "payload": _json_safe(payload),
        "text_preview": text_preview,
    }


async def _fetch_paginated_debug(
    client: httpx.AsyncClient, token: str, path: str, limit: int = 100, max_pages: int = 5
) -> dict:
    all_items: List[dict] = []
    pages_info: List[dict] = []

    for page in range(1, max_pages + 1):
        result = await _rd_get_debug(
            client,
            token,
            path,
            params={"page": page, "page_size": limit},
        )

        pages_info.append(
            {
                "page": page,
                "status_code": result["status_code"],
                "text_preview": result["text_preview"],
            }
        )

        if not result["ok"]:
            return {
                "ok": False,
                "items": all_items,
                "pages": pages_info,
                "error": f"HTTP {result['status_code']} em {path}",
                "payload": result["payload"],
            }

        items = _safe_list(result["payload"])
        if not items:
            break

        all_items.extend(_json_safe(items))

        if len(items) < limit:
            break

    return {
        "ok": True,
        "items": _json_safe(all_items),
        "pages": _json_safe(pages_info),
        "error": None,
        "payload": None,
    }


async def _fetch_segment_contacts_debug(
    client: httpx.AsyncClient,
    token: str,
    segmentation_id: str,
    limit: int = 125,
    max_pages: int = 10,
) -> dict:
    all_items: List[dict] = []
    pages_info: List[dict] = []

    for page in range(1, max_pages + 1):
        result = await _rd_get_debug(
            client,
            token,
            f"/segmentations/{segmentation_id}/contacts",
            params={"page": page, "page_size": limit},
        )

        pages_info.append(
            {
                "page": page,
                "status_code": result["status_code"],
                "text_preview": result["text_preview"],
            }
        )

        if not result["ok"]:
            return {
                "ok": False,
                "items": all_items,
                "pages": pages_info,
                "error": f"HTTP {result['status_code']} em /segmentations/{segmentation_id}/contacts",
                "payload": result["payload"],
            }

        items = _safe_list(result["payload"])
        if not items:
            break

        all_items.extend(_json_safe(items))

        if len(items) < limit:
            break

    return {
        "ok": True,
        "items": _json_safe(all_items),
        "pages": _json_safe(pages_info),
        "error": None,
        "payload": None,
    }


async def _fetch_email_metrics_debug(client: httpx.AsyncClient, token: str) -> dict:
    result = await _rd_get_debug(client, token, "/analytics/emails")
    if not result["ok"]:
        return {
            "ok": False,
            "metrics": {},
            "error": f"HTTP {result['status_code']} em /analytics/emails",
            "text_preview": result["text_preview"],
            "payload": result["payload"],
        }

    payload = result["payload"] if isinstance(result["payload"], dict) else {}
    return {
        "ok": True,
        "metrics": _json_safe(payload),
        "error": None,
        "text_preview": result["text_preview"],
        "payload": _json_safe(payload),
    }


async def _fetch_lp_analytics(
    client: httpx.AsyncClient, token: str, conversion_identifier: str
) -> dict:
    result = await _rd_get_debug(
        client,
        token,
        "/analytics/conversions",
        params={
            "asset_type": "LandingPage",
            "conversion_identifier": conversion_identifier,
        },
    )
    if not result["ok"] or not isinstance(result["payload"], dict):
        return {"visits_count": 0, "conversions_count": 0, "conversion_rate": 0.0}

    data = result["payload"]
    if isinstance(data, list):
        data = data[0] if data else {}

    return {
        "visits_count": int(data.get("visits_count") or 0),
        "conversions_count": int(data.get("conversions_count") or 0),
        "conversion_rate": float(data.get("conversion_rate") or 0.0),
    }


async def _create_run(client_id: int) -> int:
    if using_postgres():
        return await db_fetchval(
            """
            INSERT INTO rd_sync_runs (client_id, status, started_at)
            VALUES ($1, $2, $3)
            RETURNING id
            """,
            client_id,
            "running",
            _now(),
        )
    else:
        cursor = await db_execute(
            """
            INSERT INTO rd_sync_runs (client_id, status, started_at)
            VALUES (?, ?, ?)
            """,
            client_id,
            "running",
            _now().isoformat(),
        )
        return cursor.lastrowid


async def _finish_run(run_id: int, status: str, summary: dict = None, error: str = None):
    if using_postgres():
        await db_execute(
            """
            UPDATE rd_sync_runs
            SET status = $1, finished_at = $2, summary = $3, error = $4
            WHERE id = $5
            """,
            status,
            _now(),
            _jsonb(summary or {}),
            error,
            run_id,
        )
    else:
        await db_execute(
            """
            UPDATE rd_sync_runs
            SET status = ?, finished_at = ?, summary = ?, error = ?
            WHERE id = ?
            """,
            status,
            _now().isoformat(),
            _jsonb(summary or {}),
            error,
            run_id,
        )


async def _upsert_snapshot(client_id: int, object_type: str, object_key: str, payload: dict):
    if using_postgres():
        await db_execute(
            """
            INSERT INTO rd_sync_snapshots (client_id, object_type, object_key, payload, synced_at)
            VALUES ($1, $2, $3, $4, $5)
            ON CONFLICT (client_id, object_type, object_key)
            DO UPDATE SET payload = $4, synced_at = $5
            """,
            client_id,
            object_type,
            object_key,
            _jsonb(payload),
            _now(),
        )
    else:
        exists = await db_fetchval(
            "SELECT 1 FROM rd_sync_snapshots WHERE client_id = ? AND object_type = ? AND object_key = ?",
            client_id,
            object_type,
            object_key,
        )
        if exists:
            await db_execute(
                "UPDATE rd_sync_snapshots SET payload = ?, synced_at = ? WHERE client_id = ? AND object_type = ? AND object_key = ?",
                _jsonb(payload),
                _now().isoformat(),
                client_id,
                object_type,
                object_key,
            )
        else:
            await db_execute(
                "INSERT INTO rd_sync_snapshots (client_id, object_type, object_key, payload, synced_at) VALUES (?, ?, ?, ?, ?)",
                client_id,
                object_type,
                object_key,
                _jsonb(payload),
                _now().isoformat(),
            )


async def _save_summary(client_id: int, summary: dict):
    if using_postgres():
        await db_execute(
            """
            INSERT INTO rd_sync_summaries (client_id, summary, updated_at)
            VALUES ($1, $2, $3)
            ON CONFLICT (client_id)
            DO UPDATE SET summary = $2, updated_at = $3
            """,
            client_id,
            _jsonb(summary),
            _now(),
        )
    else:
        exists = await db_fetchval(
            "SELECT 1 FROM rd_sync_summaries WHERE client_id = ?", client_id
        )
        if exists:
            await db_execute(
                "UPDATE rd_sync_summaries SET summary = ?, updated_at = ? WHERE client_id = ?",
                _jsonb(summary),
                _now().isoformat(),
                client_id,
            )
        else:
            await db_execute(
                "INSERT INTO rd_sync_summaries (client_id, summary, updated_at) VALUES (?, ?, ?)",
                client_id,
                _jsonb(summary),
                _now().isoformat(),
            )


def _pick_object_key(item: dict, prefix: str, index: int) -> str:
    key = (
        item.get("id")
        or item.get("uuid")
        or item.get("identifier")
        or item.get("email")
        or f"{prefix}_{index}"
    )
    return str(key)


def _lead_identity(lead: dict, index: int) -> str:
    return str(lead.get("uuid") or lead.get("id") or lead.get("email") or f"lead_{index}")


def _extract_metrics(data: dict) -> dict:
    open_rate = 0.0
    click_rate = 0.0

    for key in ("open_rate", "opens_rate", "avg_open_rate"):
        val = data.get(key)
        if val is not None:
            try:
                open_rate = float(val)
                break
            except Exception:
                pass

    for key in ("click_rate", "clicks_rate", "avg_click_rate", "ctr"):
        val = data.get(key)
        if val is not None:
            try:
                click_rate = float(val)
                break
            except Exception:
                pass

    return {
        "open_rate": open_rate,
        "click_rate": click_rate,
        "raw": data,
    }


async def run_full_sync(client_id: int):
    await ensure_sync_tables()
    run_id = await _create_run(client_id)

    summary = None

    try:
        token = await get_valid_mkt_token(client_id)

        module_errors: Dict[str, str] = {}
        module_debug: Dict[str, dict] = {}

        async with httpx.AsyncClient(timeout=45.0) as client:
            # Parallel fetching of main modules
            (
                res_lp,
                res_seg,
                res_wf,
                res_cp,
                res_metrics,
            ) = await asyncio.gather(
                _fetch_paginated_debug(client, token, "/landing_pages", limit=100),
                _fetch_paginated_debug(client, token, "/segmentations", limit=100),
                _fetch_paginated_debug(client, token, "/workflows", limit=100),
                _fetch_paginated_debug(client, token, "/campaigns", limit=100),
                _fetch_email_metrics_debug(client, token),
                return_exceptions=True,
            )

            # Processing Landing Pages
            landing_pages = []
            if not isinstance(res_lp, Exception) and res_lp["ok"]:
                landing_pages = res_lp["items"]
                # LP Analytics can also be done in parallel if needed, but let's do it sequentially for now
                # to avoid hitting rate limits too fast, or use a limited gather.
                for i, item in enumerate(landing_pages):
                    conv_id = (
                        item.get("conversion_identifier") or item.get("identifier") or ""
                    )
                    if conv_id:
                        item["public_url"] = f"https://conteudo.rdstation.com/{conv_id}"
                        try:
                            lp_analytics = await _fetch_lp_analytics(
                                client, token, conv_id
                            )
                            item.update(lp_analytics)
                        except Exception:
                            pass
                    else:
                        item["public_url"] = ""

                    await _upsert_snapshot(
                        client_id,
                        "landing_page",
                        _pick_object_key(item, "landing_page", i),
                        item,
                    )
                module_debug["landing_pages"] = res_lp
            else:
                module_errors["landing_pages"] = str(res_lp)

            # Processing Segmentations and Leads
            segmentations = []
            unique_leads: List[dict] = []
            seen_leads: Set[str] = set()
            leads_debug = []

            if not isinstance(res_seg, Exception) and res_seg["ok"]:
                segmentations = res_seg["items"]
                for i, item in enumerate(segmentations):
                    await _upsert_snapshot(
                        client_id,
                        "segmentation",
                        _pick_object_key(item, "segmentation", i),
                        item,
                    )

                # Fetch contacts for each segmentation
                # We limit this to avoid excessive calls
                for segmentation in segmentations[:15]:
                    seg_id = (
                        segmentation.get("id")
                        or segmentation.get("uuid")
                        or segmentation.get("identifier")
                    )
                    if not seg_id:
                        continue

                    contacts_res = await _fetch_segment_contacts_debug(
                        client, token, str(seg_id), limit=100, max_pages=10
                    )
                    leads_debug.append(
                        {
                            "segmentation_id": str(seg_id),
                            "ok": contacts_res["ok"],
                            "count": len(contacts_res["items"]),
                        }
                    )

                    if contacts_res["ok"]:
                        contacts = contacts_res["items"]
                        segmentation["contacts_count"] = len(contacts)
                        await _upsert_snapshot(
                            client_id,
                            "segmentation",
                            _pick_object_key(segmentation, "segmentation", 0),
                            segmentation,
                        )

                        for c_index, contact in enumerate(contacts):
                            identity = _lead_identity(contact, c_index)
                            if identity not in seen_leads:
                                seen_leads.add(identity)
                                unique_leads.append(contact)

                        await _upsert_snapshot(
                            client_id,
                            "segmentation_contacts",
                            str(seg_id),
                            {
                                "segmentation": segmentation,
                                "contacts_count": len(contacts),
                                "contacts_preview": contacts[:50],
                            },
                        )

                module_debug["leads"] = {"ok": True, "count": len(unique_leads)}
                for i, lead in enumerate(unique_leads[:1000]):
                    await _upsert_snapshot(
                        client_id, "lead", _pick_object_key(lead, "lead", i), lead
                    )
                module_debug["segmentations"] = res_seg
            else:
                module_errors["segmentations"] = str(res_seg)

            # Processing Workflows
            workflows = []
            if not isinstance(res_wf, Exception) and res_wf["ok"]:
                workflows = res_wf["items"]
                for i, item in enumerate(workflows):
                    await _upsert_snapshot(
                        client_id, "workflow", _pick_object_key(item, "workflow", i), item
                    )
                module_debug["workflows"] = res_wf
            else:
                module_errors["workflows"] = str(res_wf)

            # Processing Campaigns
            campaigns = []
            if not isinstance(res_cp, Exception) and res_cp["ok"]:
                campaigns = res_cp["items"]
                for i, item in enumerate(campaigns):
                    await _upsert_snapshot(
                        client_id, "campaign", _pick_object_key(item, "campaign", i), item
                    )
                module_debug["campaigns"] = res_cp
            else:
                module_errors["campaigns"] = str(res_cp)

            # Processing Metrics
            metrics_raw = {}
            if not isinstance(res_metrics, Exception) and res_metrics["ok"]:
                metrics_raw = res_metrics["metrics"]
                await _upsert_snapshot(
                    client_id, "metrics", "email_metrics", metrics_raw
                )
                module_debug["metrics"] = res_metrics
            else:
                module_errors["metrics"] = str(res_metrics)

        metrics = _extract_metrics(metrics_raw)

        summary = {
            "client_id": client_id,
            "synced_at": _now().isoformat(),
            "counts": {
                "landing_pages": len(landing_pages),
                "leads": len(unique_leads),
                "segmentations": len(segmentations),
                "workflows": len(workflows),
                "campaigns": len(campaigns),
            },
            "metrics": metrics,
            "module_errors": module_errors,
            "module_debug": module_debug,
        }

        await _save_summary(client_id, summary)
        await _finish_run(run_id, "success", summary=summary)

        return {
            "ok": True,
            "run_id": run_id,
            "summary": summary,
        }

    except Exception as e:
        summary = {
            "client_id": client_id,
            "synced_at": _now().isoformat(),
            "counts": {
                "landing_pages": 0,
                "leads": 0,
                "segmentations": 0,
                "workflows": 0,
                "campaigns": 0,
            },
            "metrics": {
                "open_rate": 0.0,
                "click_rate": 0.0,
            },
            "module_errors": {
                "sync": str(e),
            },
            "module_debug": {},
        }

        try:
            await _save_summary(client_id, summary)
        except Exception:
            pass

        try:
            await _finish_run(run_id, "error", summary=summary, error=str(e))
        except Exception:
            pass

        return {
            "ok": False,
            "run_id": run_id,
            "error": str(e),
            "summary": summary,
        }


async def get_last_summary(client_id: int):
    await ensure_sync_tables()
    return await db_fetch_one(
        """
        SELECT client_id, summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )


async def get_last_run(client_id: int):
    await ensure_sync_tables()
    return await db_fetch_one(
        """
        SELECT *
        FROM rd_sync_runs
        WHERE client_id = $1
        ORDER BY id DESC
        LIMIT 1
        """,
        client_id,
    )


async def list_snapshots(client_id: int, object_type: str | None = None):
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
