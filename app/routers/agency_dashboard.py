"""
Dashboard consolidado da agência — visão única de todos os clientes.
Agrega métricas, ranking de performance, alertas críticos, delta mensal
e portfolio classificado (at_risk / expansion / maintenance).

Endpoints adicionados:
  GET  /api/agency/stats         — KPIs rápidos para o header do dashboard
  POST /api/agency/run-all-sync  — dispara sync em lote para todos os clientes
"""
import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks

from app.database import db_fetch_all, db_fetch_one, db_execute, db_fetchall

router = APIRouter()
logger = logging.getLogger(__name__)

# fix #1: lock para garantir que o ALTER TABLE não rode em paralelo
_active_column_ensured = False
_active_column_lock = asyncio.Lock()


async def _ensure_active_column():
    global _active_column_ensured
    if _active_column_ensured:
        return
    async with _active_column_lock:
        if _active_column_ensured:
            return
        try:
            await db_execute(
                "ALTER TABLE clients ADD COLUMN IF NOT EXISTS active BOOLEAN DEFAULT TRUE;"
            )
            _active_column_ensured = True
        except Exception:
            logger.exception("_ensure_active_column: falha ao adicionar coluna active")


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


def _build_portfolio(client_metrics: list) -> dict:
    at_risk, expansion, maintenance = [], [], []
    for m in client_metrics:
        score = m["health_score"]
        upsell = []
        if m["total_leads"] > 100:
            upsell.append("Base grande — potencial para segmentação avançada")
        if m["avg_open_rate"] > 25:
            upsell.append("Taxa de abertura acima da média — ideal para campanhas premium")
        if m["active_automations"] >= 3:
            upsell.append("Automações ativas — candidato a workflows mais complexos")
        if m["total_conversions"] > 50:
            upsell.append("Alto volume de conversões — oportunidade de upsell em CRM")
        entry = {
            "client_id": m["client_id"],
            "client_name": m["name"],
            "score": score,
            "status": m["status"],
            "summary": f"Score {score} — {m['status']}",
            "total_leads": m["total_leads"],
            "avg_open_rate": m["avg_open_rate"],
            "active_automations": m["active_automations"],
            "upsell_opportunities": upsell,
        }
        if score < 50:
            at_risk.append(entry)
        elif score >= 75 and upsell:
            expansion.append(entry)
        else:
            maintenance.append(entry)
    return {
        "at_risk": sorted(at_risk, key=lambda x: x["score"]),
        "expansion": sorted(expansion, key=lambda x: x["score"], reverse=True),
        "maintenance": sorted(maintenance, key=lambda x: x["score"], reverse=True),
    }


async def _fetch_latest_snapshot(cid: int):
    """Busca o snapshot mais recente de um cliente."""
    return await db_fetch_one(
        """
        SELECT client_id, data, created_at
        FROM rd_snapshots
        WHERE client_id = $1
        ORDER BY created_at DESC
        LIMIT 1
        """,
        cid,
    )


def _parse_snap(row) -> dict:
    if not row:
        return {}
    try:
        return json.loads(row["data"]) if isinstance(row["data"], str) else (row["data"] or {})
    except Exception:
        return {}


def _metrics_from_data(cid: int, name: str, data: dict) -> dict:
    total_leads        = _safe_int(data.get("total_leads"))
    campaigns          = data.get("recent_campaigns") or []
    avg_open           = _safe_float(data.get("avg_open_rate"))
    avg_click          = _safe_float(data.get("avg_click_rate"))
    automations        = data.get("automations") or []
    landing_pages      = data.get("landing_pages") or []
    total_conversions  = sum(lp.get("conversions", 0) for lp in landing_pages)
    active_automations = sum(1 for a in automations if a.get("status") == "active")

    health = 0
    if total_leads > 0:          health += 20
    if avg_open >= 20:            health += 20
    elif avg_open > 0:            health += 10
    if avg_click >= 3:            health += 20
    elif avg_click > 0:           health += 10
    if active_automations >= 3:   health += 20
    elif active_automations > 0:  health += 10
    if total_conversions > 0:    health += 20

    return {
        "client_id":          cid,
        "name":               name,
        "total_leads":        total_leads,
        "total_campaigns":    len(campaigns),
        "total_conversions":  total_conversions,
        "avg_open_rate":      avg_open,
        "avg_click_rate":     avg_click,
        "active_automations": active_automations,
        "health_score":       health,
        "status":             _status_label(health),
        "synced_at":          data.get("synced_at", ""),
    }


async def _build_client_metrics() -> list:
    await _ensure_active_column()
    clients = await db_fetch_all("SELECT id, name FROM clients ORDER BY name")
    if not clients:
        return []

    client_ids = [c["id"] for c in clients]
    name_map   = {c["id"]: c["name"] for c in clients}

    snap_results = await asyncio.gather(
        *[_fetch_latest_snapshot(cid) for cid in client_ids],
        return_exceptions=True,
    )

    client_metrics = []
    synced_ids = set()

    for snap in snap_results:
        if snap is None or isinstance(snap, Exception):
            continue
        cid  = snap["client_id"]
        data = _parse_snap(snap)
        client_metrics.append(_metrics_from_data(cid, name_map.get(cid, f"Cliente {cid}"), data))
        synced_ids.add(cid)

    for c in clients:
        if c["id"] not in synced_ids:
            client_metrics.append({
                "client_id":          c["id"],
                "name":               c["name"],
                "total_leads":        0,
                "total_campaigns":    0,
                "total_conversions":  0,
                "avg_open_rate":      0.0,
                "avg_click_rate":     0.0,
                "active_automations": 0,
                "health_score":       0,
                "status":             "🔴 Sem sync",
                "synced_at":          "",
            })

    return client_metrics


@router.get("/overview")
async def agency_overview():
    client_metrics = await _build_client_metrics()

    if not client_metrics:
        return {
            "status": "sem_clientes",
            "message": "Nenhum cliente cadastrado ainda",
            "totals": {},
            "ranking": [],
            "alerts": [],
            "delta": {},
            "portfolio": {"at_risk": [], "expansion": [], "maintenance": []},
        }

    synced_metrics = [m for m in client_metrics if m["synced_at"]]
    divisor_avg    = max(len(synced_metrics), 1)

    totals = {
        "total_clients":     len(client_metrics),
        "total_leads":       sum(m["total_leads"] for m in client_metrics),
        "total_campaigns":   sum(m["total_campaigns"] for m in client_metrics),
        "total_conversions": sum(m["total_conversions"] for m in client_metrics),
        "avg_open_rate":     round(sum(m["avg_open_rate"] for m in synced_metrics) / divisor_avg, 1),
        "avg_click_rate":    round(sum(m["avg_click_rate"] for m in synced_metrics) / divisor_avg, 1),
        "avg_health_score":  round(sum(m["health_score"] for m in synced_metrics) / divisor_avg, 1),
    }

    ranking   = sorted(client_metrics, key=lambda x: x["health_score"], reverse=True)[:10]
    alerts    = [m for m in client_metrics if m["health_score"] < 50]
    delta     = await _compute_monthly_delta([m["client_id"] for m in client_metrics])
    portfolio = _build_portfolio(client_metrics)

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "totals":    totals,
        "ranking":   ranking,
        "alerts":    alerts,
        "delta":     delta,
        "portfolio": portfolio,
    }


@router.get("/dashboard")
async def agency_dashboard_alias():
    return await agency_overview()


# ── /stats — KPIs rápidos para o header do dashboard ─────────────────────────
@router.get("/stats")
async def agency_stats():
    """
    Retorna KPIs resumidos para popular os cards do topo do dashboard:
      - total_clients
      - total_leads
      - avg_health_score
      - critical_clients  (score < 50)
      - clients_no_sync   (nunca sincronizados)
      - synced_clients    (com snapshot)
    """
    client_metrics = await _build_client_metrics()

    if not client_metrics:
        return {
            "total_clients":   0,
            "total_leads":     0,
            "avg_health_score": 0.0,
            "critical_clients": 0,
            "clients_no_sync":  0,
            "synced_clients":   0,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

    synced   = [m for m in client_metrics if m["synced_at"]]
    no_sync  = [m for m in client_metrics if not m["synced_at"]]
    critical = [m for m in client_metrics if m["health_score"] < 50]

    avg_health = round(
        sum(m["health_score"] for m in synced) / max(len(synced), 1), 1
    )

    return {
        "total_clients":    len(client_metrics),
        "total_leads":      sum(m["total_leads"] for m in client_metrics),
        "avg_health_score": avg_health,
        "critical_clients": len(critical),
        "clients_no_sync":  len(no_sync),
        "synced_clients":   len(synced),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


# ── /run-all-sync — dispara sync em lote para todos os clientes ──────────────
_run_all_status: dict = {"running": False, "progress": 0, "total": 0, "errors": [], "finished_at": None}


async def _run_all_sync_job():
    global _run_all_status
    try:
        clients = await db_fetchall("SELECT id, name FROM clients ORDER BY name")
        total   = len(clients)
        _run_all_status.update({"running": True, "progress": 0, "total": total, "errors": [], "finished_at": None})

        from app.services.rd_fullsync import run_full_sync_for_client

        batch_size = 3
        for i in range(0, total, batch_size):
            batch = clients[i : i + batch_size]
            results = await asyncio.gather(
                *[run_full_sync_for_client(c["id"]) for c in batch],
                return_exceptions=True,
            )
            for c, result in zip(batch, results):
                if isinstance(result, Exception):
                    _run_all_status["errors"].append(
                        {"client_id": c["id"], "name": c["name"], "error": str(result)}
                    )
            _run_all_status["progress"] = min(i + batch_size, total)
            if i + batch_size < total:
                await asyncio.sleep(1)

    except Exception:
        logger.exception("_run_all_sync_job: erro inesperado")
    finally:
        _run_all_status["running"]     = False
        _run_all_status["progress"]    = _run_all_status["total"]
        _run_all_status["finished_at"] = datetime.now(timezone.utc).isoformat()


@router.post("/run-all-sync")
async def run_all_sync(background_tasks: BackgroundTasks):
    """Dispara sync completo para todos os clientes em background (lotes de 3)."""
    if _run_all_status["running"]:
        return {
            "message": "Sync já está em andamento.",
            "progress": _run_all_status["progress"],
            "total":    _run_all_status["total"],
        }
    background_tasks.add_task(_run_all_sync_job)
    return {"message": "Sync iniciado para todos os clientes.", "status": "started"}


@router.get("/run-all-sync/status")
async def run_all_sync_status():
    """Retorna o progresso do sync em lote."""
    return _run_all_status


async def _fetch_delta_for_client(cid: int):
    now_row, prev_row = await asyncio.gather(
        db_fetch_one(
            "SELECT data FROM rd_snapshots WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1",
            cid,
        ),
        db_fetch_one(
            """
            SELECT data FROM rd_snapshots
            WHERE client_id = $1 AND created_at < NOW() - INTERVAL '25 days'
            ORDER BY created_at DESC LIMIT 1
            """,
            cid,
        ),
    )
    return _parse_snap(now_row), _parse_snap(prev_row)


async def _compute_monthly_delta(client_ids: list) -> dict:
    results = await asyncio.gather(
        *[_fetch_delta_for_client(cid) for cid in client_ids],
        return_exceptions=True,
    )

    total_leads_now = total_leads_prev = 0
    total_conv_now  = total_conv_prev  = 0

    for r in results:
        if isinstance(r, Exception):
            logger.warning("_compute_monthly_delta: erro em um cliente: %s", r)
            continue
        now_data, prev_data = r
        total_leads_now  += _safe_int(now_data.get("total_leads"))
        total_leads_prev += _safe_int(prev_data.get("total_leads"))
        total_conv_now   += sum(lp.get("conversions", 0) for lp in (now_data.get("landing_pages") or []))
        total_conv_prev  += sum(lp.get("conversions", 0) for lp in (prev_data.get("landing_pages") or []))

    def pct(now, prev):
        if prev == 0:
            return None
        return round((now - prev) / prev * 100, 1)

    return {
        "leads_now":             total_leads_now,
        "leads_prev":            total_leads_prev,
        "leads_delta_pct":       pct(total_leads_now, total_leads_prev),
        "conversions_now":       total_conv_now,
        "conversions_prev":      total_conv_prev,
        "conversions_delta_pct": pct(total_conv_now, total_conv_prev),
    }


# fix #2: serializa created_at para str
@router.get("/clients-summary")
async def clients_summary():
    await _ensure_active_column()
    clients = await db_fetch_all("SELECT id, name, created_at FROM clients ORDER BY name")
    return {
        "clients": [
            {"id": c["id"], "name": c["name"], "created_at": str(c["created_at"])}
            for c in (clients or [])
        ],
        "total": len(clients or []),
    }
