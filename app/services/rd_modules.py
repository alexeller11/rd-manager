import json
from typing import Any

from app.database import db_fetch_all, db_fetch_one


MODULE_CONFIG = {
    "landing_pages": {
        "object_type": "landing_page",
        "count_key": "landing_pages",
        "label": "Landing Pages",
    },
    "leads": {
        "object_type": "lead",
        "count_key": "leads",
        "label": "Leads",
    },
    "segmentations": {
        "object_type": "segmentation",
        "count_key": "segmentations",
        "label": "Segmentações",
    },
    "workflows": {
        "object_type": "workflow",
        "count_key": "workflows",
        "label": "Workflows",
    },
    "campaigns": {
        "object_type": "campaign",
        "count_key": "campaigns",
        "label": "Campanhas",
    },
}


def _get_module_or_raise(module_name: str) -> dict:
    cfg = MODULE_CONFIG.get(module_name)
    if not cfg:
        raise Exception(f"Módulo inválido: {module_name}")
    return cfg


def _parse_payload(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


async def get_client_module_overview(client_id: int) -> dict:
    summary_row = await db_fetch_one(
        """
        SELECT client_id, summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )

    summary = summary_row["summary"] if summary_row and summary_row.get("summary") else {}
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            summary = {}

    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    module_errors = summary.get("module_errors", {}) if isinstance(summary, dict) else {}
    synced_at = (
        summary.get("synced_at")
        if isinstance(summary, dict) and summary.get("synced_at")
        else (summary_row.get("updated_at") if summary_row else None)
    )

    modules = {}

    for module_name, cfg in MODULE_CONFIG.items():
        object_type = cfg["object_type"]
        count_key = cfg["count_key"]

        db_count_row = await db_fetch_one(
            """
            SELECT COUNT(*) AS total
            FROM rd_sync_snapshots
            WHERE client_id = $1 AND object_type = $2
            """,
            client_id,
            object_type,
        )

        db_count = int(db_count_row["total"]) if db_count_row and db_count_row.get("total") is not None else 0
        summary_count = int(counts.get(count_key, 0) or 0)

        modules[module_name] = {
            "label": cfg["label"],
            "count": db_count if db_count > 0 else summary_count,
            "db_count": db_count,
            "summary_count": summary_count,
            "error": module_errors.get(module_name),
            "synced_at": synced_at,
        }

    return {
        "client_id": client_id,
        "synced_at": synced_at,
        "modules": modules,
    }


async def get_client_module_items(client_id: int, module_name: str, limit: int = 100) -> dict:
    cfg = _get_module_or_raise(module_name)

    summary_row = await db_fetch_one(
        """
        SELECT client_id, summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )

    summary = summary_row["summary"] if summary_row and summary_row.get("summary") else {}
    if isinstance(summary, str):
        try:
            summary = json.loads(summary)
        except Exception:
            summary = {}

    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    module_errors = summary.get("module_errors", {}) if isinstance(summary, dict) else {}
    synced_at = (
        summary.get("synced_at")
        if isinstance(summary, dict) and summary.get("synced_at")
        else (summary_row.get("updated_at") if summary_row else None)
    )

    rows = await db_fetch_all(
        """
        SELECT id, object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1 AND object_type = $2
        ORDER BY synced_at DESC
        LIMIT $3
        """,
        client_id,
        cfg["object_type"],
        limit,
    ) or []

    items = []
    for row in rows:
        payload = _parse_payload(row.get("payload"))
        items.append({
            "snapshot_id": row.get("id"),
            "object_key": row.get("object_key"),
            "synced_at": row.get("synced_at"),
            "payload": payload,
        })

    return {
        "client_id": client_id,
        "module": module_name,
        "label": cfg["label"],
        "count": max(len(items), int(counts.get(cfg["count_key"], 0) or 0)),
        "error": module_errors.get(module_name),
        "synced_at": synced_at,
        "items": items,
    }
