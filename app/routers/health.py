from fastapi import APIRouter, HTTPException
from app.database import db_fetchone, db_fetchall, parse_json_field
from app.routers.clients import fetch_client

router = APIRouter()


def calc_health_score(snapshot: dict) -> dict:
    score = 0
    breakdown = {}

    leads = snapshot.get("total_leads", 0) or 0
    if leads == 0 and snapshot.get("segmentations"):
        leads = max((s.get("contacts", 0) for s in snapshot["segmentations"]), default=0)
    pts = 20 if leads > 10000 else 15 if leads > 5000 else 10 if leads > 1000 else 5 if leads > 100 else 2
    breakdown["base_leads"] = {"pts": pts, "max": 20, "label": "Tamanho da base"}
    score += pts

    open_rate = snapshot.get("avg_open_rate", 0) or 0
    pts = 25 if open_rate >= 30 else 20 if open_rate >= 20 else 12 if open_rate >= 15 else 6 if open_rate >= 10 else 0
    breakdown["open_rate"] = {"pts": pts, "max": 25, "label": "Taxa de abertura"}
    score += pts

    click_rate = snapshot.get("avg_click_rate", 0) or 0
    pts = 20 if click_rate >= 5 else 15 if click_rate >= 3 else 8 if click_rate >= 2 else 4 if click_rate >= 1 else 0
    breakdown["click_rate"] = {"pts": pts, "max": 20, "label": "Taxa de cliques"}
    score += pts

    segs = len(snapshot.get("segmentations", []) or [])
    pts = 10 if segs >= 5 else 7 if segs >= 3 else 4 if segs >= 1 else 0
    breakdown["segmentations"] = {"pts": pts, "max": 10, "label": "Segmentações"}
    score += pts

    campaigns = snapshot.get("recent_campaigns", []) or []
    pts = 15 if len(campaigns) >= 4 else 10 if len(campaigns) >= 2 else 5 if len(campaigns) >= 1 else 0
    breakdown["campaigns"] = {"pts": pts, "max": 15, "label": "Campanhas recentes"}
    score += pts

    lps = len(snapshot.get("landing_pages", []) or [])
    pts = 10 if lps >= 3 else 6 if lps >= 1 else 0
    breakdown["landing_pages"] = {"pts": pts, "max": 10, "label": "Landing pages"}
    score += pts

    if score >= 75:   status, label = "green",  "Saudável"
    elif score >= 45: status, label = "yellow", "Atenção"
    else:             status, label = "red",    "Crítico"

    return {"score": score, "status": status, "label": label, "breakdown": breakdown}


def build_alerts(snapshot: dict) -> list:
    alerts = []
    open_rate  = snapshot.get("avg_open_rate", 0) or 0
    click_rate = snapshot.get("avg_click_rate", 0) or 0
    leads      = snapshot.get("total_leads", 0) or 0
    campaigns  = snapshot.get("recent_campaigns", []) or []

    if open_rate and open_rate < 15:
        alerts.append({"type": "danger",  "title": "Taxa de abertura crítica",    "message": f"{open_rate}% está abaixo de 15%. Reengajamento urgente.", "action": "Criar campanha de reengajamento"})
    elif open_rate and open_rate < 20:
        alerts.append({"type": "warning", "title": "Taxa de abertura em queda",   "message": f"{open_rate}% abaixo do ideal. Revise assuntos e horários.", "action": "Otimizar linhas de assunto"})
    if leads and leads < 500:
        alerts.append({"type": "warning", "title": "Base de leads pequena",       "message": f"Apenas {leads} contatos. Estratégia de captação urgente.", "action": "Criar estratégia de captação"})
    if not campaigns:
        alerts.append({"type": "warning", "title": "Sem campanhas recentes",      "message": "Nenhuma campanha de email encontrada.", "action": "Planejar calendário de envios"})
    if click_rate and click_rate < 1:
        alerts.append({"type": "warning", "title": "Taxa de cliques muito baixa", "message": f"{click_rate}% CTR. Revise CTAs e relevância do conteúdo.", "action": "Revisar estratégia de CTA"})
    if not alerts:
        alerts.append({"type": "success", "title": "Tudo em ordem", "message": "Nenhum alerta crítico identificado.", "action": None})
    return alerts


@router.get("/score/{client_id}")
async def get_health_score(client_id: int):
    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1",
        client_id
    )
    snap = parse_json_field(row["data"]) if row else {}
    result = calc_health_score(snap)
    result.update({"client_id": client_id, "client_name": client["name"], "has_data": bool(snap.get("total_leads"))})
    return result


@router.get("/all")
async def get_all_health_scores():
    clients = await db_fetchall("SELECT * FROM clients ORDER BY name")
    scores = []
    for c in clients:
        row = await db_fetchone(
            "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", c["id"]
        )
        snap = parse_json_field(row["data"]) if row else {}
        result = calc_health_score(snap)
        result.update({"client_id": c["id"], "client_name": c["name"],
                       "segment": c.get("segment", ""), "has_data": bool(snap.get("total_leads"))})
        scores.append(result)
    scores.sort(key=lambda x: x["score"])
    return scores


@router.get("/alerts/{client_id}")
async def get_alerts(client_id: int):
    row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    if not row:
        return {"alerts": [{"type": "warning", "title": "Sem dados", "message": "Sincronize o RD Station primeiro.", "action": None}], "total": 1}
    snap = parse_json_field(row["data"])
    alerts = build_alerts(snap)
    return {"alerts": alerts, "total": len(alerts)}
