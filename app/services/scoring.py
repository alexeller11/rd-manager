from typing import Any, Dict, List


def _safe_items(block: dict | None) -> list:
    if not block or not isinstance(block, dict):
        return []
    items = block.get("items")
    return items if isinstance(items, list) else []


def _safe_count(block: dict | None) -> int:
    if not block or not isinstance(block, dict):
        return 0
    value = block.get("count", 0)
    try:
        return int(value)
    except Exception:
        return 0


def _extract_metrics(raw_metrics: dict | None) -> dict:
    """
    Tenta extrair métricas de email de diferentes formatos de payload.
    """
    if not raw_metrics or not isinstance(raw_metrics, dict):
        return {
            "open_rate": 0.0,
            "click_rate": 0.0,
            "delivered": 0,
            "opens": 0,
            "clicks": 0,
        }

    payload = raw_metrics.get("email_metrics", raw_metrics)

    if isinstance(payload, dict):
        # formatos comuns
        open_rate = payload.get("open_rate") or payload.get("opens_rate") or 0
        click_rate = payload.get("click_rate") or payload.get("clicks_rate") or 0
        delivered = payload.get("delivered") or payload.get("total_delivered") or 0
        opens = payload.get("opens") or payload.get("total_opens") or 0
        clicks = payload.get("clicks") or payload.get("total_clicks") or 0

        try:
            open_rate = float(open_rate or 0)
        except Exception:
            open_rate = 0.0

        try:
            click_rate = float(click_rate or 0)
        except Exception:
            click_rate = 0.0

        try:
            delivered = int(delivered or 0)
        except Exception:
            delivered = 0

        try:
            opens = int(opens or 0)
        except Exception:
            opens = 0

        try:
            clicks = int(clicks or 0)
        except Exception:
            clicks = 0

        return {
            "open_rate": open_rate,
            "click_rate": click_rate,
            "delivered": delivered,
            "opens": opens,
            "clicks": clicks,
        }

    return {
        "open_rate": 0.0,
        "click_rate": 0.0,
        "delivered": 0,
        "opens": 0,
        "clicks": 0,
    }


def _score_from_open_rate(open_rate: float) -> int:
    if open_rate >= 25:
        return 20
    if open_rate >= 20:
        return 16
    if open_rate >= 15:
        return 12
    if open_rate >= 10:
        return 8
    if open_rate > 0:
        return 4
    return 0


def _score_from_click_rate(click_rate: float) -> int:
    if click_rate >= 4:
        return 15
    if click_rate >= 3:
        return 12
    if click_rate >= 2:
        return 8
    if click_rate >= 1:
        return 4
    if click_rate > 0:
        return 2
    return 0


def build_client_score(client: dict, overview: dict | None = None) -> dict:
    """
    Gera score executivo de cliente com base em:
    - conexão RD
    - landing pages
    - segmentações
    - automações/workflows
    - campanhas
    - métricas de email
    """
    overview = overview or {}

    rd_connected = bool(
        client.get("rd_token_set")
        or client.get("rd_connected")
        or client.get("rd_token")
        or client.get("rd_refresh_token")
    )

    landing_pages = overview.get("landing_pages", {})
    segmentations = overview.get("segmentations", {})
    workflows = overview.get("workflows", {})
    campaigns = overview.get("campaigns", {})
    metrics = _extract_metrics(overview.get("metrics", {}))

    landing_count = _safe_count(landing_pages)
    segmentation_count = _safe_count(segmentations)
    workflow_count = _safe_count(workflows)
    campaign_count = _safe_count(campaigns)

    score = 0
    reasons: List[str] = []
    alerts: List[str] = []
    actions: List[str] = []

    # Conexão RD
    if rd_connected:
        score += 20
        reasons.append("RD conectado")
    else:
        alerts.append("Cliente sem RD conectado")
        actions.append("Conectar a conta RD para liberar leitura automática dos dados")

    # Landing pages
    if landing_count >= 5:
        score += 15
        reasons.append("Boa quantidade de landing pages ativas")
    elif landing_count >= 1:
        score += 8
        reasons.append("Possui landing pages, mas ainda há espaço para expansão")
    else:
        alerts.append("Nenhuma landing page encontrada")
        actions.append("Mapear e analisar as páginas principais de captação")

    # Segmentações
    if segmentation_count >= 5:
        score += 15
        reasons.append("Base segmentada com boa profundidade")
    elif segmentation_count >= 1:
        score += 8
        reasons.append("Há segmentações, mas elas podem ser refinadas")
    else:
        alerts.append("Nenhuma segmentação encontrada")
        actions.append("Criar segmentações acionáveis para campanhas e automações")

    # Workflows / automações
    if workflow_count >= 3:
        score += 15
        reasons.append("Automação ativa com múltiplos fluxos")
    elif workflow_count >= 1:
        score += 8
        reasons.append("Há automações, mas o nível ainda é básico")
    else:
        alerts.append("Nenhuma automação encontrada")
        actions.append("Criar pelo menos um fluxo de nutrição e um fluxo de reativação")

    # Campanhas
    if campaign_count >= 5:
        score += 10
        reasons.append("Volume de campanhas consistente")
    elif campaign_count >= 1:
        score += 5
        reasons.append("Campanhas existem, mas sem consistência clara")
    else:
        alerts.append("Nenhuma campanha encontrada")
        actions.append("Ativar campanhas recorrentes com calendário e objetivo definidos")

    # Métricas
    email_open_score = _score_from_open_rate(metrics["open_rate"])
    email_click_score = _score_from_click_rate(metrics["click_rate"])
    score += email_open_score + email_click_score

    if metrics["open_rate"] > 0:
        reasons.append(f"Open rate atual: {metrics['open_rate']:.1f}%")
    else:
        alerts.append("Sem leitura clara de taxa de abertura")
        actions.append("Revisar campanhas de email e tracking de métricas")

    if metrics["click_rate"] > 0:
        reasons.append(f"Click rate atual: {metrics['click_rate']:.1f}%")
    else:
        alerts.append("Sem leitura clara de taxa de clique")
        actions.append("Revisar CTA, segmentação e qualidade da copy dos emails")

    # Limites
    if score > 100:
        score = 100

    # Prioridade
    if score < 40:
        priority = "alta"
    elif score < 70:
        priority = "média"
    else:
        priority = "baixa"

    # Ações padrão adicionais
    if not actions:
        actions.append("Aprimorar campanhas com base nos dados atuais")
        actions.append("Criar rotina de otimização contínua")

    summary = (
        f"{client.get('name', 'Cliente')} está com score {score}/100. "
        f"Prioridade {priority}. "
        f"Principais gaps: {', '.join(alerts[:3]) if alerts else 'operação relativamente estável'}."
    )

    return {
        "client_id": client.get("id"),
        "client_name": client.get("name"),
        "score": score,
        "priority": priority,
        "rd_connected": rd_connected,
        "counts": {
            "landing_pages": landing_count,
            "segmentations": segmentation_count,
            "workflows": workflow_count,
            "campaigns": campaign_count,
        },
        "metrics": metrics,
        "reasons": reasons,
        "alerts": alerts,
        "actions": actions,
        "summary": summary,
    }


def build_agency_score(client_scores: List[dict]) -> dict:
    if not client_scores:
        return {
            "score": 0,
            "clients_total": 0,
            "connected_total": 0,
            "high_priority_total": 0,
            "ranking": [],
            "alerts": ["Nenhum cliente cadastrado na base"],
            "weekly_priorities": [],
        }

    total_clients = len(client_scores)
    connected_total = sum(1 for c in client_scores if c.get("rd_connected"))
    high_priority_total = sum(1 for c in client_scores if c.get("priority") == "alta")
    avg_score = round(sum(c.get("score", 0) for c in client_scores) / total_clients)

    ranking = sorted(client_scores, key=lambda x: x.get("score", 0), reverse=True)

    alerts = []
    if connected_total < total_clients:
        alerts.append("Existem clientes sem RD conectado")
    if high_priority_total > 0:
        alerts.append(f"{high_priority_total} cliente(s) exigem prioridade alta")
    if avg_score < 60:
        alerts.append("A maturidade média da carteira ainda está baixa")

    weekly_priorities = []
    if connected_total < total_clients:
        weekly_priorities.append("Conectar todos os clientes pendentes ao RD")
    if high_priority_total > 0:
        weekly_priorities.append("Atuar primeiro nos clientes de prioridade alta")
    weekly_priorities.append("Mapear landing pages e fluxos mais estratégicos")
    weekly_priorities.append("Criar operação recorrente de segmentação e reativação")

    return {
        "score": avg_score,
        "clients_total": total_clients,
        "connected_total": connected_total,
        "high_priority_total": high_priority_total,
        "ranking": ranking,
        "alerts": alerts,
        "weekly_priorities": weekly_priorities,
    }
