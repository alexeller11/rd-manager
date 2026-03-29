from app.database import db_fetch_all, db_fetch_one
from app.services.scoring import build_client_score


async def build_agency_alerts() -> dict:
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

    critical = []
    warnings = []
    actions = []

    for client in clients:
        summary_row = await db_fetch_one(
            """
            SELECT summary, updated_at
            FROM rd_sync_summaries
            WHERE client_id = $1
            """,
            client["id"],
        )

        summary_payload = summary_row["summary"] if summary_row and summary_row.get("summary") else {}
        score_data = build_client_score(client, summary_payload)

        if score_data["priority"] == "alta":
            critical.append({
                "client_id": client["id"],
                "client_name": client["name"],
                "message": f"{client['name']} está com prioridade alta e exige ação rápida.",
            })

        for alert in score_data["alerts"]:
            warnings.append({
                "client_id": client["id"],
                "client_name": client["name"],
                "message": alert,
            })

        for action in score_data["actions"]:
            actions.append({
                "client_id": client["id"],
                "client_name": client["name"],
                "message": action,
            })

    return {
        "critical": critical[:10],
        "warnings": warnings[:20],
        "actions": actions[:20],
        "totals": {
            "critical": len(critical),
            "warnings": len(warnings),
            "actions": len(actions),
        },
    }
