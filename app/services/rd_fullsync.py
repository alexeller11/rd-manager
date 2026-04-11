import json
import httpx
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

from app.auth_core import get_valid_mkt_token
from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval, using_postgres

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


async def _rd_get_debug(token: str, path: str, params: Optional[dict] = None) -> dict:
    async with httpx.AsyncClient(timeout=45.0) as client:
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


async def _fetch_paginated_debug(token: str, path: str, limit: int = 100, max_pages: int = 5) -> dict:
    all_items: List[dict] = []
    pages_info: List[dict] = []

    for page in range(1, max_pages + 1):
        result = await _rd_get_debug(
            token,
            path,
            params={"page": page, "limit": limit},
        )

        pages_info.append({
            "page": page,
            "status_code": result["status_code"],
            "text_preview": result["text_preview"],
        })

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
    token: str,
    segmentation_id: str,
    limit: int = 100,
    max_pages: int = 5,
) -> dict:
    all_items: List[dict] = []
    pages_info: List[dict] = []

    for page in range(1, max_pages + 1):
        result = await _rd_get_debug(
            token,
            f"/segmentations/{segmentation_id}/contacts",
            params={"page": page, "limit": limit},
        )

        pages_info.append({
            "page": page,
            "status_code": result["status_code"],
            "text_preview": result["text_preview"],
        })

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


async def _fetch_email_metrics_debug(token: str) -> dict:
    result = await _rd_get_debug(token, "/analytics/emails")
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


def _pick_object_key(item: dict, fallback_prefix: str, index: int) -> str:
    for key in ("id", "uuid", "identifier", "slug", "name", "title", "email"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value)
    return f"{fallback_prefix}_{index}"


def _lead_identity(item: dict, index: int) -> str:
    for key in ("email", "id", "uuid", "identifier"):
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip().lower()
    return f"lead_{index}"


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
        VALUES ($1, $2, $3, $4::jsonb, $5)
        ON CONFLICT (client_id, object_type, object_key)
        DO UPDATE SET
            payload = EXCLUDED.payload,
            synced_at = EXCLUDED.synced_at
        """,
        client_id,
        object_type,
        object_key,
        _jsonb(payload),
        _now(),
    )


async def _save_summary(client_id: int, summary: dict):
    await db_execute(
        """
        INSERT INTO rd_sync_summaries (client_id, summary, updated_at)
        VALUES ($1, $2::jsonb, $3)
        ON CONFLICT (client_id)
        DO UPDATE SET
            summary = EXCLUDED.summary,
            updated_at = EXCLUDED.updated_at
        """,
        client_id,
        _jsonb(summary),
        _now(),
    )


async def _create_run(client_id: int) -> int:
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


async def _finish_run(run_id: int, status: str, summary: dict | None = None, error: str | None = None):
    await db_execute(
        """
        UPDATE rd_sync_runs
        SET status = $2, finished_at = $3, summary = $4::jsonb, error = $5
        WHERE id = $1
        """,
        run_id,
        status,
        _now(),
        _jsonb(summary or {}),
        str(error) if error else None,
    )


    # Tenta capturar métricas de diversas formas (direta ou aninhada)
    data = metrics_payload or {}
    open_rate = 0.0
    click_rate = 0.0
    visitors = 0
    conversions = 0

    # Possíveis chaves para taxa de abertura
    for key in ("open_rate", "opens_rate", "avg_open_rate", "opening_rate"):
        val = data.get(key)
        if val is not None:
            try:
                open_rate = float(val)
                break
            except: pass

    # Possíveis chaves para taxa de clique
    for key in ("click_rate", "clicks_rate", "avg_click_rate", "ctr"):
        val = data.get(key)
        if val is not None:
            try:
                click_rate = float(val)
                break
            except: pass

    # Possíveis chaves para volume (para modules como LPs)
    for key in ("visitors_count", "visits", "view_count", "total_visits"):
        val = data.get(key)
        if val is not None:
            try:
                visitors = int(val)
                break
            except: pass

    for key in ("conversions_count", "conversions", "leads_count", "leads"):
        val = data.get(key)
        if val is not None:
            try:
                conversions = int(val)
                break
            except: pass

    return {
        "open_rate": open_rate,
        "click_rate": click_rate,
        "visitors": visitors,
        "conversions": conversions,
    }


async def run_full_sync(client_id: int):
    await ensure_sync_tables()
    run_id = await _create_run(client_id)

    summary = None

    try:
        token = await get_valid_mkt_token(client_id)

        landing_pages: List[dict] = []
        segmentations: List[dict] = []
        workflows: List[dict] = []
        campaigns: List[dict] = []
        metrics_raw: dict = {}
        module_errors: Dict[str, str] = {}
        module_debug: Dict[str, dict] = {}

        unique_leads: List[dict] = []
        seen_leads: Set[str] = set()

        try:
            result = await _fetch_paginated_debug(token, "/landing_pages", limit=100, max_pages=25)
            module_debug["landing_pages"] = result
            if result["ok"]:
                landing_pages = result["items"]
                for i, item in enumerate(landing_pages):
                    # Tenta enriquecer o item com métricas se estiverem disponíveis no payload
                    item["_metrics"] = _extract_metrics(item)
                    await _upsert_snapshot(client_id, "landing_page", _pick_object_key(item, "landing_page", i), item)
            else:
                module_errors["landing_pages"] = result["error"]
        except Exception as e:
            module_errors["landing_pages"] = str(e)

        try:
            result = await _fetch_paginated_debug(token, "/segmentations", limit=100, max_pages=25)
            module_debug["segmentations"] = result
            if result["ok"]:
                segmentations = result["items"]
                for i, item in enumerate(segmentations):
                    await _upsert_snapshot(client_id, "segmentation", _pick_object_key(item, "segmentation", i), item)
            else:
                module_errors["segmentations"] = result["error"]
        except Exception as e:
            module_errors["segmentations"] = str(e)

        try:
            leads_debug = []

            for segmentation in segmentations:
                segmentation_id = (
                    segmentation.get("id")
                    or segmentation.get("uuid")
                    or segmentation.get("identifier")
                )

                if not segmentation_id:
                    continue

                contacts_result = await _fetch_segment_contacts_debug(
                    token,
                    str(segmentation_id),
                    limit=100,
                    max_pages=25,
                )

                leads_debug.append({
                    "segmentation_id": str(segmentation_id),
                    "ok": contacts_result["ok"],
                    "error": contacts_result["error"],
                    "pages": contacts_result["pages"],
                    "count": len(contacts_result["items"]),
                })

                contacts = contacts_result["items"]
                
                # Atualiza a contagem na segmentação original para facilitar a exibição
                segmentation["contacts_count"] = len(contacts)
                await _upsert_snapshot(client_id, "segmentation", _pick_object_key(segmentation, "segmentation", 0), segmentation)

                for c_index, contact in enumerate(contacts):
                    identity = _lead_identity(contact, c_index)
                    if identity in seen_leads:
                        continue
                    seen_leads.add(identity)
                    unique_leads.append(contact)

                await _upsert_snapshot(
                    client_id,
                    "segmentation_contacts",
                    str(segmentation_id),
                    {
                        "segmentation": segmentation,
                        "contacts_count": len(contacts),
                        "contacts_preview": contacts[:50],
                    },
                )

            module_debug["leads"] = {
                "ok": True,
                "details": leads_debug,
                "count": len(unique_leads),
            }

            for i, lead in enumerate(unique_leads[:1500]):
                await _upsert_snapshot(client_id, "lead", _pick_object_key(lead, "lead", i), lead)

        except Exception as e:
            module_errors["leads"] = str(e)

        try:
            result = await _fetch_paginated_debug(token, "/workflows", limit=100, max_pages=25)
            module_debug["workflows"] = result
            if result["ok"]:
                workflows = result["items"]
                for i, item in enumerate(workflows):
                    await _upsert_snapshot(client_id, "workflow", _pick_object_key(item, "workflow", i), item)
            else:
                module_errors["workflows"] = result["error"]
        except Exception as e:
            module_errors["workflows"] = str(e)

        try:
            result = await _fetch_paginated_debug(token, "/campaigns", limit=100, max_pages=25)
            module_debug["campaigns"] = result
            if result["ok"]:
                campaigns = result["items"]
                for i, item in enumerate(campaigns):
                    await _upsert_snapshot(client_id, "campaign", _pick_object_key(item, "campaign", i), item)
            else:
                module_errors["campaigns"] = result["error"]
        except Exception as e:
            module_errors["campaigns"] = str(e)

        try:
            result = await _fetch_email_metrics_debug(token)
            module_debug["metrics"] = result
            if result["ok"]:
                metrics_raw = result["metrics"]
                await _upsert_snapshot(client_id, "metrics", "email_metrics", metrics_raw)
            else:
                module_errors["metrics"] = result["error"]
        except Exception as e:
            module_errors["metrics"] = str(e)

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
