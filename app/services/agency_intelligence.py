from datetime import datetime, timezone

from app.database import db_execute, db_fetch_all, db_fetch_one
from app.routers.clients import fetch_client


# ==============================
# INIT TABLE
# ==============================

async def ensure_snapshots_table():
    await db_execute("""
        CREATE TABLE IF NOT EXISTS client_snapshots (
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            score INTEGER,
            data JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
    """)


# ==============================
# GERAR SNAPSHOT
# ==============================

async def generate_snapshot(client_id: int, score: int, data: dict):
    await ensure_snapshots_table()

    await db_execute("""
        INSERT INTO client_snapshots (client_id, score, data, created_at)
        VALUES ($1, $2, $3, $4)
    """, client_id, score, data, datetime.now(timezone.utc))


# ==============================
# ÚLTIMO SNAPSHOT
# ==============================

async def get_last_snapshot(client_id: int):
    return await db_fetch_one("""
        SELECT *
        FROM client_snapshots
        WHERE client_id = $1
        ORDER BY created_at DESC
        LIMIT 1
    """, client_id)


# ==============================
# SNAPSHOT ANTERIOR
# ==============================

async def get_previous_snapshot(client_id: int):
    return await db_fetch_one("""
        SELECT *
        FROM client_snapshots
        WHERE client_id = $1
        ORDER BY created_at DESC
        OFFSET 1
        LIMIT 1
    """, client_id)


# ==============================
# COMPARAÇÃO
# ==============================

async def compare_snapshots(client_id: int):
    last = await get_last_snapshot(client_id)
    prev = await get_previous_snapshot(client_id)

    if not last or not prev:
        return None

    delta = last["score"] - prev["score"]

    return {
        "last_score": last["score"],
        "previous_score": prev["score"],
        "delta": delta
    }


# ==============================
# ALERTAS AUTOMÁTICOS
# ==============================

async def generate_alerts(client_id: int, score: int, data: dict):
    alerts = []

    if score < 50:
        alerts.append("Score crítico: cliente com baixa maturidade")

    if data.get("landing_pages", 0) == 0:
        alerts.append("Sem landing pages ativas")

    if data.get("workflows", 0) == 0:
        alerts.append("Sem automações configuradas")

    if data.get("campaigns", 0) == 0:
        alerts.append("Sem campanhas ativas")

    if data.get("segmentations", 0) == 0:
        alerts.append("Sem segmentação da base")

    return alerts


# ==============================
# PRIORIDADES AUTOMÁTICAS
# ==============================

async def generate_priorities(alerts):
    priorities = []

    for alert in alerts:
        if "Score crítico" in alert:
            priorities.append("Reestruturar estratégia do cliente")

        elif "landing" in alert:
            priorities.append("Criar landing page estratégica")

        elif "automações" in alert:
            priorities.append("Criar fluxo de automação")

        elif "campanhas" in alert:
            priorities.append("Ativar campanhas de aquisição")

        elif "segmentação" in alert:
            priorities.append("Organizar base e segmentações")

    return priorities


# ==============================
# RESUMO DA AGÊNCIA
# ==============================

async def build_agency_overview():
    clients = await db_fetch_all("SELECT id, name FROM clients")

    total_score = 0
    ranking = []
    alerts_global = []
    priorities_global = []

    for c in clients:
        client_id = c["id"]

        # dados fake por enquanto (vamos ligar com RD depois)
        data = {
            "landing_pages": 0,
            "workflows": 0,
            "campaigns": 0,
            "segmentations": 0
        }

        score = 40  # placeholder

        total_score += score

        alerts = await generate_alerts(client_id, score, data)
        priorities = await generate_priorities(alerts)

        alerts_global.extend(alerts)
        priorities_global.extend(priorities)

        ranking.append({
            "client_id": client_id,
            "client_name": c["name"],
            "score": score,
            "priority": "alta" if score < 50 else "média",
            "summary": "Cliente com baixo nível de estrutura",
            "actions": priorities,
            "counts": data,
            "rd_connected": False
        })

    avg_score = int(total_score / len(clients)) if clients else 0

    return {
        "agency": {
            "score": avg_score,
            "clients_total": len(clients),
            "connected_total": 0,
            "high_priority_total": len([r for r in ranking if r["priority"] == "alta"]),
            "ranking": ranking,
            "alerts": alerts_global[:5],
            "weekly_priorities": priorities_global[:5]
        }
    }
