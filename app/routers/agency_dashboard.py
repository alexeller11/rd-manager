import json

from fastapi import APIRouter

from app.database import db_execute, db_fetch_all, db_fetch_one, using_postgres
from app.services.scoring import build_client_score
from app.services.executive_briefing import generate_executive_briefing

router = APIRouter()


async def _ensure_sync_summary_table():
    if using_postgres():
        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS rd_sync_summaries (
                client_id INTEGER PRIMARY KEY,
                summary JSONB NOT NULL DEFAULT '{}'::jsonb,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        return

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_summaries (
            client_id INTEGER PRIMARY KEY,
            summary TEXT NOT NULL DEFAULT '{}',
            updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def _parse_summary(value):
    if not value:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    if isinstance(value, dict):
        return value
    return {}


@router.get("/overview")
async def agency_overview():
    await _ensure_sync_summary_table()
    clients = await db_fetch_all(
        """
        SELECT
            c.id,
            c.name,
            c.segment,
            c.website,
            c.description,
            CASE
                WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
                WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
                ELSE FALSE
            END AS rd_connected,
            CASE
                WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
                WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
                ELSE FALSE
            END AS rd_token_set
        FROM clients c
        LEFT JOIN rd_credentials rc
            ON rc.client_id = c.id
        ORDER BY c.id DESC
        """
    ) or []

    ranking = []
    alerts = []
    weekly_priorities = []
    at_risk = []
    expansion = []
    maintenance = []

    for client in clients:
        summary_row = await db_fetch_one(
            """
            SELECT summary, updated_at
            FROM rd_sync_summaries
            WHERE client_id = $1
            """,
            client["id"],
        )

        summary = _parse_summary(summary_row["summary"] if summary_row else {})
        if summary_row and summary_row.get("updated_at") and not summary.get("synced_at"):
            summary["synced_at"] = str(summary_row["updated_at"])

        score_data = build_client_score(client, summary)
        ranking.append(score_data)

        if score_data["stage"] == "urgente":
            at_risk.append(score_data)
            weekly_priorities.append(f"{client['name']} exige ação imediata para reduzir risco.")
        elif score_data["stage"] == "expansão":
            expansion.append(score_data)
            weekly_priorities.append(f"{client['name']} tem espaço claro para upsell e expansão.")
        else:
            maintenance.append(score_data)

        for alert in score_data["alerts"][:2]:
            alerts.append(f"{client['name']}: {alert}")

    ranking = sorted(ranking, key=lambda x: x["score"])

    agency_score = 0
    if ranking:
        agency_score = int(sum(item["score"] for item in ranking) / len(ranking))

    potential_revenue = (
        len(at_risk) * 500
        + len(expansion) * 1200
        + len(maintenance) * 300
    )

    # Gerar Briefing de IA
    agency_data = {
        "score": agency_score,
        "clients_total": len(clients),
        "connected_total": sum(1 for c in clients if c.get("rd_connected")),
        "high_priority_total": len(at_risk),
        "alerts": alerts[:10],
        "weekly_priorities": weekly_priorities[:10],
        "ranking": ranking,
        "portfolio": {
            "at_risk": at_risk,
            "expansion": expansion,
            "maintenance": maintenance,
        },
        "director_view": {
            "at_risk_total": len(at_risk),
            "expansion_total": len(expansion),
            "maintenance_total": len(maintenance),
            "potential_revenue": potential_revenue,
        },
    }

    executive_briefing = "O Briefing da IA está sendo gerado..."
    try:
        executive_briefing = await generate_executive_briefing(agency_data)
    except Exception as e:
        executive_briefing = f"Erro ao gerar briefing de IA: {str(e)}"

    return {
        "agency": {
            **agency_data,
            "executive_briefing": executive_briefing
        }
    }
