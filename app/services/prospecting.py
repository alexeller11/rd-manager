from typing import Any


def _normalize_text(value: Any) -> str:
    return str(value or "").strip()


def build_prospect_diagnosis(payload: dict) -> dict:
    company_name = _normalize_text(payload.get("company_name"))
    niche = _normalize_text(payload.get("niche"))
    city = _normalize_text(payload.get("city"))
    website = _normalize_text(payload.get("website"))
    instagram = _normalize_text(payload.get("instagram"))

    weak_points = []
    opportunities = []
    sales_angles = []
    action_plan = []

    if not website:
        weak_points.append("A empresa não informou site, o que pode indicar presença digital limitada ou pouco estruturada.")
        opportunities.append("Criar uma base de captação mais previsível com landing pages e campanhas.")
        sales_angles.append("Hoje a operação depende mais da força comercial do que de um funil previsível.")
        action_plan.append("Mapear canais atuais de entrada e estruturar uma jornada mínima de captação.")

    if website:
        weak_points.append("Mesmo com site, a empresa pode não estar convertendo o tráfego em oportunidades reais se não houver captação estruturada.")
        opportunities.append("Transformar o site em canal de geração de leads com páginas focadas por oferta.")
        sales_angles.append("Ter site não significa gerar demanda; o ponto é transformar visita em oportunidade.")
        action_plan.append("Auditar páginas principais e identificar onde falta CTA, oferta e captura.")

    if niche:
        opportunities.append(f"No nicho de {niche}, automação e segmentação costumam destravar ganho comercial com mais velocidade.")
        sales_angles.append(f"Empresas de {niche} geralmente perdem oportunidades quando não segmentam base e não acompanham intenção.")
        action_plan.append(f"Criar uma esteira de campanhas e nutrição específica para o nicho de {niche}.")

    if city:
        sales_angles.append(f"Há espaço para posicionar a marca com mais força em {city} por meio de campanhas e presença digital mais organizada.")

    if instagram:
        opportunities.append("Aproveitar a rede social como porta de entrada para leads, em vez de deixá-la só como vitrine.")
        action_plan.append("Conectar campanhas, Instagram e landing pages em uma jornada clara de captação.")

    weak_points.append("Sem automações e sem leitura contínua da base, a empresa tende a depender de esforço manual para vender.")
    weak_points.append("Sem segmentação, a comunicação tende a ser genérica e a taxa de conversão fica menor.")
    opportunities.append("Implantar automações de nutrição, reativação e recuperação de oportunidades.")
    opportunities.append("Usar segmentação para falar com cada tipo de lead no momento certo.")
    sales_angles.append("O crescimento trava quando o negócio depende só de esforço manual e não de processo.")
    sales_angles.append("A maior oportunidade costuma estar em organizar melhor o que já entra, antes mesmo de escalar investimento.")
    action_plan.append("Estruturar segmentação mínima por perfil, interesse e estágio do lead.")
    action_plan.append("Criar automações de boas-vindas, nutrição e reativação.")
    action_plan.append("Definir rotina mensal de campanhas e leitura de performance.")

    potential = "Médio"
    if not website or not instagram:
        potential = "Alto"
    if website and instagram:
        potential = "Médio/Alto"

    executive_summary = (
        f"{company_name or 'A empresa'} apresenta oportunidade clara de evolução comercial. "
        f"O maior ganho tende a vir de organizar captação, segmentação e automação, reduzindo dependência de esforço manual."
    )

    return {
        "company_name": company_name,
        "niche": niche,
        "city": city,
        "website": website,
        "instagram": instagram,
        "potential": potential,
        "executive_summary": executive_summary,
        "weak_points": weak_points,
        "opportunities": opportunities,
        "sales_angles": sales_angles,
        "action_plan": action_plan,
    }
