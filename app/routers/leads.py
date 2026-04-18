import json
from fastapi import APIRouter, HTTPException
from app.ai_service import call_ai_json, SYSTEM_EXPERT

router = APIRouter()


def _extract_json(raw) -> dict:
    """Garante retorno de dict mesmo se a IA retornar string."""
    if isinstance(raw, dict):
        return raw
    try:
        start = str(raw).index("{")
        end = str(raw).rindex("}") + 1
        return json.loads(str(raw)[start:end])
    except Exception:
        return {"raw": str(raw)}


@router.post("/analyze-base")
async def analyze_leads(data: dict):
    """
    Analisa a base de leads e retorna diagnostico estruturado em JSON.
    Espera no body: total_leads, hot, warm, cold, dead, engagement_rate,
    sources (dict), segments (list), campaigns (list), client_name (str).
    """
    try:
        client_name = data.get("client_name") or "o cliente"
        total = data.get("total_leads") or data.get("total") or 0
        hot = data.get("hot") or 0
        warm = data.get("warm") or 0
        cold = data.get("cold") or 0
        dead = data.get("dead") or 0
        engagement_rate = data.get("engagement_rate") or 0
        sources = data.get("sources") or {}
        segments = data.get("segments") or []
        campaigns = data.get("campaigns") or []

        prompt = f"""Voce e um Estrategista Senior de CRM e Marketing Digital.

Analise a base de leads do cliente '{client_name}' e gere um diagnostico executivo acionavel.

DADOS DA BASE:
- Total de leads: {total}
- Quentes (ativos nos ultimos 7 dias): {hot}
- Mornos (8-30 dias): {warm}
- Frios (31-90 dias): {cold}
- Mortos (mais de 90 dias ou sem interacao): {dead}
- Taxa de engajamento: {engagement_rate}%
- Origens dos leads: {sources}
- Segmentacoes existentes: {segments}
- Campanhas recentes: {campaigns}

Retorne APENAS um JSON valido, sem markdown, sem texto antes ou depois:
{{
  "overview": {{
    "health": "saudavel|atencao|critico",
    "summary": "string — situacao geral em 2-3 linhas diretas e praticas"
  }},
  "segments": [
    {{
      "name": "string",
      "size_estimate": "string",
      "engagement": "alto|medio|baixo",
      "priority": "alta|media|baixa"
    }}
  ],
  "opportunities": [
    {{
      "opportunity": "string",
      "estimated_impact": "string",
      "effort": "baixo|medio|alto"
    }}
  ],
  "bottlenecks": [
    {{
      "issue": "string",
      "root_cause": "string",
      "urgency": "alta|media|baixa"
    }}
  ],
  "reactivation_candidates": {{
    "count_estimate": "string",
    "suggested_approach": "string",
    "message_angle": "string"
  }},
  "recommended_campaigns": [
    {{
      "name": "string",
      "objective": "string",
      "target_segment": "string",
      "suggested_channel": "string"
    }}
  ],
  "actions": [
    {{
      "action": "string",
      "when": "imediato|esta-semana|este-mes",
      "owner": "agencia|cliente",
      "expected_gain": "string"
    }}
  ]
}}"""

        result = await call_ai_json(prompt, system=SYSTEM_EXPERT, max_tokens=2500)
        return {"ok": True, "analysis": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na analise de leads: {str(e)}")


@router.post("/segment")
async def segment_leads(data: dict):
    """
    Gera segmentacoes acionaveis para a base de leads.
    Espera no body: dados da base ou lista de leads.
    """
    try:
        client_name = data.get("client_name") or "o cliente"
        total = data.get("total_leads") or data.get("total") or 0
        sources = data.get("sources") or {}
        segments_existing = data.get("segments") or []
        engagement_rate = data.get("engagement_rate") or 0

        prompt = f"""Voce e um especialista em segmentacao e CRM para agencias digitais.

Crie segmentacoes uteis, praticas e acionaveis para a base do cliente '{client_name}'.

CONTEXTO DA BASE:
- Total de leads: {total}
- Taxa de engajamento atual: {engagement_rate}%
- Origens conhecidas: {sources}
- Segmentacoes ja existentes: {segments_existing}

Retorne APENAS um JSON valido, sem markdown, sem texto antes ou depois:
{{
  "total_segments_suggested": 0,
  "segments": [
    {{
      "name": "string",
      "description": "string",
      "entry_criteria": "string — regra clara para entrada nesse segmento",
      "estimated_size": "string",
      "priority": "alta|media|baixa",
      "recommended_action": "string — o que fazer com esse segmento",
      "risk_of_inaction": "string — o que acontece se nao atuar",
      "suggested_campaign_type": "string"
    }}
  ],
  "quick_wins": [
    {{
      "action": "string",
      "segment_target": "string",
      "expected_result": "string",
      "effort": "baixo|medio|alto"
    }}
  ]
}}"""

        result = await call_ai_json(prompt, system=SYSTEM_EXPERT, max_tokens=2000)
        return {"ok": True, "segments": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro na segmentacao de leads: {str(e)}")
