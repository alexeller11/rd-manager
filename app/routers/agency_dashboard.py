from fastapi import APIRouter, Depends, HTTPException

from app.auth_core import get_current_user
from app.database import db_fetch_all, db_fetch_one

router = APIRouter()


def _build_score_from_summary(client: dict, summary_payload: dict | None) -> dict:
    summary_payload = summary_payload or {}

    counts = summary_payload.get("counts", {}) if isinstance(summary_payload, dict) else {}
    metrics = summary_payload.get("metrics", {}) if isinstance(summary_payload, dict) else {}

    landing_pages = int(counts.get("landing_pages", 0) or 0)
    segmentations = int(counts.get("segmentations", 0) or 0)
    workflows = int(counts.get("workflows", 0) or 0)
    campaigns = int(counts.get("campaigns", 0) or 0)

    rd_connected = bool(client.get("rd_connected") or client.get("rd_token_set"))

    score = 0
    alerts = []
    actions = []
    reasons = []

    if rd_connected:
        score += 25
        reasons.append("RD conectada")
    else:
        alerts.append("Cliente sem RD conectado")
        actions.append("Conectar a conta RD para liberar leitura completa")

    if landing_pages > 0:
        score += min(15, landing_pages * 3)
        reasons.append(f"{landing_pages} landing page(s) detectada(s)")
    else:
        alerts.append("Sem landing pages sincronizadas")
        actions.append("Rodar sync da RD e mapear páginas principais")

    if segmentations > 0:
        score += min(15, segmentations * 2)
        reasons.append(f"{segmentations} segmentação(ões) encontrada(s)")
    else:
        alerts.append("Sem segmentações sincronizadas")
        actions.append("Criar segmentações acionáveis da base")

    if workflows > 0:
        score += min(20, workflows * 4)
        reasons.append(f"{workflows} automação(ões) encontrada(s)")
    else:
        alerts.append("Sem automações ativas")
        actions.append("Criar fluxo de nutrição e fluxo de reativação")

    if campaigns > 0:
        score += min(15, campaigns * 3)
        reasons.append(f"{campaigns} campanha(s) encontrada(s)")
    else:
        alerts.append("Sem campanhas recentes")
        actions.append("Ativar campanhas recorrentes com calendário")

    if score > 100:
        score = 100

    if score < 40:
        priority = "alta"
    elif score < 70:
        priority = "média"
    else:
        priority = "baixa"

    summary_text = (
        f"{client.get('name', 'Cliente')} está com score {score}/100. "
        f"Prioridade {priority}. "
        f"Principais gaps: {', '.join(alerts[:3]) if alerts else 'estrutura consistente'}."
    )

    return {
        "client_id": client.get("id"),
        "client_name": client.get("name"),
        "score": score,
        "priority": priority,
        "summary": summary_text,
        "alerts": alerts,
        "actions": actions,
        "reasons": reasons,
        "rd_connected": rd_connected,
        "counts": {
            "landing_pages": landing_pages,
            "segmentations": segmentations,
            "workflows": workflows,
            "campaigns": campaigns,
        },
        "metrics": metrics if isinstance(metrics, dict) else {},
    }


@router.get("/overview", dependencies=[Depends(get_current_user)])
async def agency_overview():
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
    )

    clients = clients or []

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

        summary_payload = summary_row["summary"] if summary_row and summary_row.get("summary") else None
        item = _build_score_from_summary(client, summary_payload)

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
    if avg_score < 60:
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

    summary_payload = summary_row["summary"] if summary_row and summary_row.get("summary") else None
    score_data = _build_score_from_summary(client, summary_payload)

    return {
        "client": client,
        "score_data": score_data,
        "sync_summary": summary_payload,
    }
