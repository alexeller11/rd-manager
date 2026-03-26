from typing import Any, Dict, List


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value or 0)
    except Exception:
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value or 0)
    except Exception:
        return default


def calculate_score(summary: dict | None) -> int:
    """
    Score 0-100 a partir do resumo sincronizado da RD.
    """
    summary = summary or {}
    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}

    landing_pages = _safe_int(counts.get("landing_pages"))
    segmentations = _safe_int(counts.get("segmentations"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    open_rate = _safe_float(metrics.get("open_rate"))
    click_rate = _safe_float(metrics.get("click_rate"))

    score = 0

    # estrutura
    score += min(20, landing_pages * 4)
    score += min(20, segmentations * 3)
    score += min(20, workflows * 5)
    score += min(15, campaigns * 3)

    # performance
    if open_rate >= 25:
        score += 15
    elif open_rate >= 20:
        score += 12
    elif open_rate >= 15:
        score += 8
    elif open_rate > 0:
        score += 4

    if click_rate >= 4:
        score += 10
    elif click_rate >= 3:
        score += 8
    elif click_rate >= 2:
        score += 5
    elif click_rate > 0:
        score += 2

    return max(0, min(100, score))


def build_client_score(client: dict, summary: dict | None) -> dict:
    summary = summary or {}
    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}

    score = calculate_score(summary)

    rd_connected = bool(client.get("rd_connected") or client.get("rd_token_set"))

    landing_pages = _safe_int(counts.get("landing_pages"))
    segmentations = _safe_int(counts.get("segmentations"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    alerts: List[str] = []
    actions: List[str] = []

    if not rd_connected:
        alerts.append("Cliente sem RD conectada")
        actions.append("Conectar a conta RD")

    if landing_pages == 0:
        alerts.append("Sem landing pages sincronizadas")
        actions.append("Rodar sync e mapear páginas estratégicas")

    if segmentations == 0:
        alerts.append("Sem segmentações úteis")
        actions.append("Criar segmentações acionáveis")

    if workflows == 0:
        alerts.append("Sem automações ativas")
        actions.append("Criar fluxo de nutrição e reativação")

    if campaigns == 0:
        alerts.append("Sem campanhas recentes")
        actions.append("Ativar calendário de campanhas")

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
        "rd_connected": rd_connected,
        "counts": {
            "landing_pages": landing_pages,
            "segmentations": segmentations,
            "workflows": workflows,
            "campaigns": campaigns,
        },
        "metrics": {
            "open_rate": _safe_float(metrics.get("open_rate")),
            "click_rate": _safe_float(metrics.get("click_rate")),
        },
    }
