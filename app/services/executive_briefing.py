from datetime import datetime, timezone
from typing import Any, Dict

from app.ai_service import call_ai


async def generate_executive_briefing(agency_data: Dict[str, Any]) -> str:
    """
    Gera um briefing estratégico para o diretor da agência com base nos dados de todos os clientes.
    Utiliza o sistema de redundância de IA (Gemini -> SambaNova -> etc).
    """
    
    total_clients = agency_data.get("clients_total", 0)
    connected_clients = agency_data.get("connected_total", 0)
    high_priority = agency_data.get("high_priority_total", 0)
    agency_score = agency_data.get("score", 0)
    
    # Extrair ranking para contexto
    ranking = agency_data.get("ranking", [])
    top_3 = ranking[-3:] if len(ranking) >= 3 else ranking
    bottom_3 = ranking[:3] if len(ranking) >= 3 else ranking
    
    portfolio = agency_data.get("portfolio", {})
    at_risk_names = [c["client_name"] for c in portfolio.get("at_risk", [])]
    expansion_names = [c["client_name"] for c in portfolio.get("expansion", [])]
    
    prompt = f"""
Você é um Consultor Estratégico de Elite para donos de agências de marketing.
Sua missão é analisar o estado da agência e dar um briefing direto, crítico e acionável.

DADOS DA AGÊNCIA:
- Score Geral da Agência: {agency_score}/100
- Total de Clientes: {total_clients}
- Clientes com RD Conectada: {connected_clients}
- Clientes em Estado Crítico/Urgente: {high_priority}

CLIENTES EM ALTA PRIORIDADE (RISCO): {", ".join(at_risk_names) if at_risk_names else "Nenhum"}
OPORTUNIDADES DE EXPANSÃO: {", ".join(expansion_names) if expansion_names else "Nenhuma"}

MELHORES SCORES: {[f"{c['client_name']} ({c['score']})" for c in top_3]}
PIORES SCORES: {[f"{c['client_name']} ({c['score']})" for c in bottom_3]}

DIRETRIZES:
1. Comece com uma análise do "Estado Geral" da agência.
2. Seja específico sobre quem corre risco de cancelar (Churn) e por quê.
3. Aponte oportunidades de ouro (Upsell) baseadas nos dados de expansão.
4. Finalize com 3 "Ações Imediatas" para o Diretor hoje.
5. Foco em ROBÚSTEZ e DADOS REAIS. Se houver muitos clientes desconectados, critique isso.

Limite a 4 parágrafos curtos e objetivos. Responda em Português do Brasil.
"""

    return await call_ai(
        prompt=prompt,
        system="Você é o Cérebro Estratégico da Agência. Seu tom é executivo, direto e focado em lucro e retenção.",
        temperature=0.7
    )
