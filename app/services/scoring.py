from typing import Any


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
    summary = summary or {}
    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    module_errors = summary.get("module_errors", {}) if isinstance(summary, dict) else {}

    landing_pages = _safe_int(counts.get("landing_pages"))
    leads = _safe_int(counts.get("leads"))
    segmentations = _safe_int(counts.get("segmentations"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    open_rate = _safe_float(metrics.get("open_rate"))
    click_rate = _safe_float(metrics.get("click_rate"))

    score = 100

    if landing_pages == 0:
        score -= 20

    if segmentations == 0:
        score -= 15

    if workflows == 0:
        score -= 15

    if campaigns == 0:
        score -= 10

    if leads < 100:
        score -= 15
    elif leads < 300:
        score -= 5

    if open_rate > 0 and open_rate < 15:
        score -= 5

    if click_rate > 0 and click_rate < 2:
        score -= 5

    if module_errors.get("campaigns"):
        score -= 5

    return max(0, min(100, score))


def classify_stage(score: int, counts: dict, module_errors: dict | None = None) -> str:
    module_errors = module_errors or {}

    leads = _safe_int(counts.get("leads"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    if score < 45:
        return "urgente"

    if leads >= 100 and (workflows == 0 or campaigns == 0 or bool(module_errors.get("campaigns"))):
        return "expansão"

    return "manutenção"


def estimate_growth_potential(counts: dict, score: int) -> int:
    leads = _safe_int(counts.get("leads"))
    landing_pages = _safe_int(counts.get("landing_pages"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    potential = 0

    if leads >= 100:
        potential += 2
    if leads >= 300:
        potential += 2
    if landing_pages > 0:
        potential += 1
    if workflows == 0:
        potential += 2
    if campaigns == 0:
        potential += 2
    if score < 70:
        potential += 1

    return potential


def build_client_score(client: dict, summary: dict | None) -> dict:
    summary = summary or {}
    counts = summary.get("counts", {}) if isinstance(summary, dict) else {}
    metrics = summary.get("metrics", {}) if isinstance(summary, dict) else {}
    module_errors = summary.get("module_errors", {}) if isinstance(summary, dict) else {}

    score = calculate_score(summary)
    rd_connected = bool(client.get("rd_connected") or client.get("rd_token_set"))

    landing_pages = _safe_int(counts.get("landing_pages"))
    leads = _safe_int(counts.get("leads"))
    segmentations = _safe_int(counts.get("segmentations"))
    workflows = _safe_int(counts.get("workflows"))
    campaigns = _safe_int(counts.get("campaigns"))

    counts_payload = {
        "landing_pages": landing_pages,
        "leads": leads,
        "segmentations": segmentations,
        "workflows": workflows,
        "campaigns": campaigns,
    }

    stage = classify_stage(score, counts_payload, module_errors)
    growth_potential = estimate_growth_potential(counts_payload, score)

    alerts = []
    actions = []
    upsell_opportunities = []

    if not rd_connected:
        alerts.append("A conta ainda está sem RD conectada, o que impede leitura contínua da operação.")
        actions.append("Conectar a conta RD para liberar monitoramento completo.")

    if landing_pages == 0:
        alerts.append("A empresa está sem landing pages sincronizadas, reduzindo previsibilidade na captação.")
        actions.append("Mapear e estruturar páginas de captação alinhadas às ofertas principais.")

    if segmentations == 0:
        alerts.append("A base ainda não demonstra segmentações úteis, o que reduz precisão da comunicação.")
        actions.append("Criar segmentações acionáveis por perfil, origem e estágio do lead.")

    if workflows == 0:
        alerts.append("A operação está sem automações ativas, aumentando dependência de esforço manual.")
        actions.append("Implementar fluxo de nutrição e reativação para ganhar escala.")

    if campaigns == 0 and not module_errors.get("campaigns"):
        alerts.append("A empresa está sem campanhas ativas, o que reduz geração de demanda e previsibilidade de vendas.")
        actions.append("Ativar calendário de campanhas com objetivo e rotina definidos.")

    if leads < 100:
        alerts.append("O volume de leads atual está baixo para uma operação previsível de crescimento.")
        actions.append("Reforçar canais de captação e melhorar conversão das páginas.")

    if module_errors.get("campaigns"):
        alerts.append("A leitura de campanhas não está disponível para esta conta ou plano da RD.")
        actions.append("Validar se a conta possui permissão ou plano compatível para campanhas.")

    if module_errors.get("metrics"):
        alerts.append("As métricas de e-mail não puderam ser lidas pela integração.")
        actions.append("Revisar endpoint, permissão e disponibilidade das métricas da conta.")

    if leads >= 100 and workflows == 0:
        upsell_opportunities.append("Base com leads suficiente para vender automação e nutrição.")
    if leads >= 100 and campaigns == 0 and not module_errors.get("campaigns"):
        upsell_opportunities.append("Conta pronta para ganho de demanda com campanhas ativas.")
    if segmentations == 0 and leads > 0:
        upsell_opportunities.append("Há espaço para vender estratégia de segmentação da base.")
    if landing_pages > 0 and leads < 100:
        upsell_opportunities.append("As páginas existem, mas a captação pode ser otimizada para aumentar volume de leads.")

    if stage == "urgente":
        priority_label = "urgente"
    elif stage == "expansão":
        priority_label = "expansão"
    else:
        priority_label = "manutenção"

    summary_text = (
        f"{client.get('name', 'Cliente')} está com score {score}/100 e estágio {priority_label}. "
        f"Landing Pages: {landing_pages}, Leads: {leads}, Segmentações: {segmentations}, "
        f"Workflows: {workflows}, Campanhas: {campaigns}."
    )

    return {
        "client_id": client.get("id"),
        "client_name": client.get("name"),
        "score": score,
        "priority": priority_label,
        "stage": priority_label,
        "summary": summary_text,
        "alerts": alerts,
        "actions": actions,
        "upsell_opportunities": upsell_opportunities,
        "growth_potential": growth_potential,
        "rd_connected": rd_connected,
        "counts": counts_payload,
        "metrics": {
            "open_rate": _safe_float(metrics.get("open_rate")),
            "click_rate": _safe_float(metrics.get("click_rate")),
        },
        "last_sync": summary.get("synced_at"),
    }


def calculate_lead_score(contact: dict | None) -> int:
    """Calcula um score simples de 0 a 100 para um lead individual.

    A ideia aqui é ter um critério consistente para a rota /leads-analysis,
    alinhado com a lógica de health score mas focado no lead.
    """
    contact = contact or {}

    conversions = _safe_int(contact.get("conversions") or contact.get("conversion_count"))
    tags = contact.get("tags") or contact.get("tag_list") or []

    if isinstance(tags, str):
        tags_list = [t.strip() for t in tags.split(",") if t.strip()]
    elif isinstance(tags, list):
        tags_list = tags
    else:
        tags_list = []

    base = 30

    if conversions >= 1:
        base += 20
    if conversions >= 3:
        base += 20

    lowered = [str(t).lower() for t in tags_list]
    if any(word in lowered for word in ["cliente", "customer", "comprou", "pago"]):
        base += 20

    return max(0, min(100, base))
