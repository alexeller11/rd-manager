"""
Dashboard consolidado da agência — visão única de todos os clientes.
Agrega métricas, ranking de performance, alertas críticos e delta mensal.
"""
import json
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException

from app.database import db_fetchall, db_fetchone

router = APIRouter(prefix="/agency", tags=["agency"])


def _safe_float(val, default=0.0) -> float:
    try:
        return float(val) if val is not None else default
    except Exception:
        return default


def _safe_int(val, default=0) -> int:
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


def _status_label(score: float) -> str:
    if score >= 85:
        return "🟢 Excelente"
    if score >= 70:
        return "🟡 Bom"
    if score >= 50:
        return "🟠 Atenção"
    return "🔴 Crítico"


@router.get("/dashboard")
async def agency_dashboard():
    """
    Retorna visão consolidada de todos os clientes da agência:
    - Totais agregados
    - Ranking top 10 por health score
    - Clientes críticos (score < 50)
    - Delta mês atual vs mês anterior
    """

    # 1. Lista todos os clientes ativos
    clients = await db_fetchall(
        "SELECT id, name FROM clients WHERE active = true ORDER BY name"
    )
    if not clients:
        return {
            "status": "sem_clientes",
            "message": "Nenhum cliente ativo encontrado",
            "totals": {},
            "ranking": [],
            "alerts": [],
            "delta": {},
        }

    client_ids = [c["id"] for c in clients]

    # 2. Busca snapshots mais recentes de cada cliente
    snapshots = []
    for cid in client_ids:
        row = await db_fetchone(
            """
            SELECT client_id, data, created_at
            FROM rd_snapshots
            WHERE client_id = $1
            ORDER BY created_at DESC
            LIMIT 1
            """,
            cid,
        )
        if row:
            snapshots.append(row)

    # 3. Monta mapa client_id → nome
    name_map = {c["id"]: c["name"] for c in clients}

    # 4. Processa métricas por cliente
    client_metrics = []
    for snap in snapshots:
        cid = snap["client_id"]
        try:
            data = json.loads(snap["data"]) if isinstance(snap["data"], str) else snap["data"]
        except Exception:
            data = {}

        total_leads = _safe_int(data.get("total_leads"))
        campaigns = data.get("recent_campaigns") or []
        avg_open = _safe_float(data.get("avg_open_rate"))
        avg_click = _safe_float(data.get("avg_click_rate"))
        automations = data.get("automations") or []
        landing_pages = data.get("landing_pages") or []

        total_sent = sum(c.get("sent", 0) for c in campaigns)
        total_conversions = sum(lp.get("conversions", 0) for lp in landing_pages)
        active_automations = sum(1 for a in automations if a.get("status") == "active")

        # Health score simples baseado nas métricas disponíveis
        health = 0
        if total_leads > 0:
            health += 20
        if avg_open >= 20:
            health += 20
        elif avg_open > 0:
            health += 10
        if avg_click >= 3:
            health += 20
        elif avg_click > 0:
            health += 10
        if active_automations >= 3:
            health += 20
        elif active_automations > 0:
            health += 10
        if total_conversions > 0:
            health += 20

        client_metrics.append({
            "client_id": cid,
            "name": name_map.get(cid, f"Cliente {cid}"),
            "total_leads": total_leads,
            "total_campaigns": len(campaigns),
            "total_conversions": total_conversions,
            "avg_open_rate": avg_open,
            "avg_click_rate": avg_click,
            "active_automations": active_automations,
            "health_score": health,
            "status": _status_label(health),
            "synced_at": data.get("synced_at", ""),
        })

    # 5. Totais agregados
    totals = {
        "total_clients": len(client_metrics),
        "total_leads": sum(m["total_leads"] for m in client_metrics),
        "total_campaigns": sum(m["total_campaigns"] for m in client_metrics),
        "total_conversions": sum(m["total_conversions"] for m in client_metrics),
        "avg_open_rate": round(
            sum(m["avg_open_rate"] for m in client_metrics) / max(len(client_metrics), 1), 1
        ),
        "avg_click_rate": round(
            sum(m["avg_click_rate"] for m in client_metrics) / max(len(client_metrics), 1), 1
        ),
        "avg_health_score": round(
            sum(m["health_score"] for m in client_metrics) / max(len(client_metrics), 1), 1
        ),
    }

    # 6. Ranking por health score (top 10)
    ranking = sorted(client_metrics, key=lambda x: x["health_score"], reverse=True)[:10]

    # 7. Alertas críticos (score < 50)
    alerts = [m for m in client_metrics if m["health_score"] < 50]

    # 8. Delta mês atual vs anterior — compara snapshots
    delta = await _compute_monthly_delta(client_ids)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals": totals,
        "ranking": ranking,
        "alerts": alerts,
        "delta": delta,
    }


async def _compute_monthly_delta(client_ids: list[int]) -> dict:
    """
    Calcula variação percentual de leads e conversões
    entre o snapshot mais recente e o snapshot de ~30 dias atrás.
    """
    total_leads_now = 0
    total_leads_prev = 0
    total_conv_now = 0
    total_conv_prev = 0

    for cid in client_ids:
        # Snapshot mais recente
        now_row = await db_fetchone(
            """
            SELECT data FROM rd_snapshots
            WHERE client_id = $1
            ORDER BY created_at DESC LIMIT 1
            """,
            cid,
        )
        # Snapshot de ~30 dias atrás
        prev_row = await db_fetchone(
            """
            SELECT data FROM rd_snapshots
            WHERE client_id = $1
              AND created_at < NOW() - INTERVAL '25 days'
            ORDER BY created_at DESC LIMIT 1
            """,
            cid,
        )

        def parse_snap(row):
            if not row:
                return {}
            try:
                return json.loads(row["data"]) if isinstance(row["data"], str) else row["data"]
            except Exception:
                return {}

        now_data = parse_snap(now_row)
        prev_data = parse_snap(prev_row)

        total_leads_now += _safe_int(now_data.get("total_leads"))
        total_leads_prev += _safe_int(prev_data.get("total_leads"))

        lps_now = now_data.get("landing_pages") or []
        lps_prev = prev_data.get("landing_pages") or []
        total_conv_now += sum(lp.get("conversions", 0) for lp in lps_now)
        total_conv_prev += sum(lp.get("conversions", 0) for lp in lps_prev)

    def pct(now, prev):
        if prev == 0:
            return None
        return round((now - prev) / prev * 100, 1)

    return {
        "leads_now": total_leads_now,
        "leads_prev": total_leads_prev,
        "leads_delta_pct": pct(total_leads_now, total_leads_prev),
        "conversions_now": total_conv_now,
        "conversions_prev": total_conv_prev,
        "conversions_delta_pct": pct(total_conv_now, total_conv_prev),
    }


@router.get("/clients-summary")
async def clients_summary():
    """Lista resumida de todos os clientes com status rápido."""
    clients = await db_fetchall(
        "SELECT id, name, created_at FROM clients WHERE active = true ORDER BY name"
    )
    return {"clients": [dict(c) for c in (clients or [])], "total": len(clients or [])}
