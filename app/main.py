from fastapi import APIRouter, Depends, HTTPException

from app.auth_core import get_current_user
from app.database import db_execute, db_fetch_all, db_fetch_one
from app.services.scoring import build_client_score, calculate_score

router = APIRouter()


async def _ensure_sync_summary_table():
    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_sync_summaries (
            client_id INTEGER PRIMARY KEY,
            summary JSONB NOT NULL,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )


@router.get("/overview", dependencies=[Depends(get_current_user)])
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
    connected_total = 0
    high_priority_total = 0

    for client in clients:
        summary_row = await db_fetch_one(
            """
            SELECT summary, updated_at
            FROM rd_sync_summaries
            WHERE client_id = $1
            """,
            client["id"],
        )

        summary_payload = None
        if summary_row and summary_row.get("summary"):
            summary_payload = summary_row["summary"]

        item = build_client_score(client, summary_payload)

        if item["rd_connected"]:
            connected_total += 1
        if item["priority"] == "alta":
            high_priority_total += 1

        ranking.append(item)

    ranking = sorted(ranking, key=lambda x: x["score"], reverse=True)

    avg_score = 0
    if ranking:
        avg_score = round(sum(item["score"] for item in ranking) / len(ranking))

    alerts = []
    if connected_total < len(clients):
        alerts.append("Existem clientes sem RD conectada")
    if high_priority_total > 0:
        alerts.append(f"{high_priority_total} cliente(s) com prioridade alta")
    if avg_score < 60 and len(clients) > 0:
        alerts.append("A maturidade média da carteira ainda está baixa")

    weekly_priorities = []
    if connected_total < len(clients):
        weekly_priorities.append("Conectar todos os clientes pendentes à RD")
    if high_priority_total > 0:
        weekly_priorities.append("Atuar primeiro nos clientes com prioridade alta")
    weekly_priorities.append("Rodar sync completo da RD nos clientes estratégicos")
    weekly_priorities.append("Transformar gargalos em plano de ação semanal")

    return {
        "agency": {
            "score": avg_score,
            "clients_total": len(clients),
            "connected_total": connected_total,
            "high_priority_total": high_priority_total,
            "ranking": ranking,
            "alerts": alerts,
            "weekly_priorities": weekly_priorities,
        },
        "clients": clients,
    }


@router.get("/client/{client_id}", dependencies=[Depends(get_current_user)])
async def agency_client_detail(client_id: int):
    await _ensure_sync_summary_table()

    client = await db_fetch_one(
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
        WHERE c.id = $1
        """,
        client_id,
    )

    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    summary_row = await db_fetch_one(
        """
        SELECT summary, updated_at
        FROM rd_sync_summaries
        WHERE client_id = $1
        """,
        client_id,
    )

    summary_payload = None
    if summary_row and summary_row.get("summary"):
        summary_payload = summary_row["summary"]

    score_data = build_client_score(client, summary_payload)

    return {
        "client": client,
        "score_data": score_data,
        "sync_summary": summary_payload,
    }
