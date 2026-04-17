"""
Flows Advanced — geração de fluxos e emails via IA com resposta JSON estruturada.
"""
import json
from fastapi import APIRouter, HTTPException
from app.ai_service import generate_text

router = APIRouter()


def _extract_json(raw: str) -> dict:
    """Tenta extrair JSON de uma string; fallback para dict com raw text."""
    try:
        start = raw.index("{")
        end = raw.rindex("}") + 1
        return json.loads(raw[start:end])
    except Exception:
        return {"raw": raw}


@router.post("/generate-flow")
async def generate_flow(data: dict):
    flow_days = int(data.get("flow_days") or 10)
    email_count = int(data.get("email_count") or 4)
    flow_type = data.get("flow_type") or "nutrição"
    goal = data.get("goal") or "conversão"
    product = data.get("product") or "não informado"
    audience = data.get("audience") or "não informado"
    awareness = data.get("awareness") or "não informado"

    prompt = f"""Você é um Arquiteto de Automação de Marketing sênior especializado em RD Station.
Gere um fluxo de automação estratégico com base nos dados abaixo.

OBJETIVO: {goal}
TIPO: {flow_type}
PRODUTO/SERVIÇO: {product}
PÚBLICO-ALVO: {audience}
NÍVEL DE CONSCIÊNCIA: {awareness}
DUR�AÇÃO: {flow_days} dias
TOTAL DE EMAILS: {email_count}

Retorne APENAS um JSON válido, sem markdown, sem texto antes ou depois, seguindo exatamente este schema:
{{
  "flow_name": "string",
  "strategy_summary": "string (2-3 linhas)",
  "trigger": "string",
  "steps": [
    {{
      "day": 0,
      "type": "email | condition | wait | action",
      "title": "string",
      "description": "string",
      "subject": "string ou null",
      "cta": "string ou null"
    }}
  ],
  "final_action": "string",
  "success_metrics": {{
    "expected_open_rate": "string",
    "expected_conversion_rate": "string",
    "estimated_roi": "string"
  }}
}}"""

    raw = await generate_text(prompt)
    result = _extract_json(raw)
    return {"ok": True, "flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    tone = data.get("tone") or "consultivo"
    objective = data.get("objective") or "gerar resposta"
    theme = data.get("theme") or "nutrição"
    cta = data.get("cta") or "responder o email"
    target = data.get("target") or "lead da base"
    context = data.get("context") or "não informado"

    prompt = f"""Você é um especialista em copywriting para email marketing B2B.
Crie um email completo com variação A/B.

Contexto: {context}
Tema: {theme}
Objetivo: {objective}
Tom de voz: {tone}
Público-alvo: {target}
CTA principal: {cta}

Retorne APENAS um JSON válido, sem markdown, sem texto antes ou depois, seguindo exatamente este schema:
{{
  "version_a": {{
    "subject": "string",
    "preheader": "string",
    "body": "string (HTML simples permitido)",
    "cta_text": "string",
    "cta_url_placeholder": "string"
  }},
  "version_b": {{
    "subject": "string",
    "preheader": "string",
    "body": "string",
    "cta_text": "string",
    "cta_url_placeholder": "string"
  }},
  "recommended_version": "A ou B",
  "reasoning": "string (por que essa versão tende a performar melhor)"
}}"""

    raw = await generate_text(prompt)
    result = _extract_json(raw)
    return {"ok": True, "email": result}
