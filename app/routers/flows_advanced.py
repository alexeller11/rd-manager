"""
Flows Advanced - geracao de fluxos e emails via IA com resposta JSON estruturada.
Usa call_ai_json para garantir saida estruturada e build_client_context para enriquecer prompts.
"""
import json
from fastapi import APIRouter, HTTPException
from app.ai_service import call_ai_json, SYSTEM_COPYWRITER, SYSTEM_STRATEGIST

router = APIRouter()


def _extract_json(raw) -> dict:
    """Garante retorno de dict mesmo se houver string."""
    if isinstance(raw, dict):
        return raw
    try:
        s = str(raw)
        start = s.index("{")
        end = s.rindex("}") + 1
        return json.loads(s[start:end])
    except Exception:
        return {"raw": str(raw)}


@router.post("/generate-flow")
async def generate_flow(data: dict):
    """
    Gera um fluxo de automacao estrategico para RD Station.
    Body: flow_days, email_count, flow_type, goal, product, audience, awareness,
          client_name, client_segment, client_description, rd_data (opcional).
    """
    try:
        flow_days = int(data.get("flow_days") or 10)
        email_count = int(data.get("email_count") or 4)
        flow_type = data.get("flow_type") or "nutricao"
        goal = data.get("goal") or "conversao"
        product = data.get("product") or "nao informado"
        audience = data.get("audience") or "nao informado"
        awareness = data.get("awareness") or "nao informado"
        client_name = data.get("client_name") or ""
        client_segment = data.get("client_segment") or ""
        client_description = data.get("client_description") or ""

        client_block = ""
        if client_name:
            client_block = f"""
CONTEXTO DO CLIENTE:
- Empresa: {client_name}
- Segmento: {client_segment}
- Descricao: {client_description}
"""

        prompt = f"""Voce e um Arquiteto de Automacao de Marketing Senior especializado em RD Station.
Gere um fluxo de automacao estrategico e detalhado com base nos dados abaixo.
{client_block}
OBJETIVO: {goal}
TIPO: {flow_type}
PRODUTO/SERVICO: {product}
PUBLICO-ALVO: {audience}
NIVEL DE CONSCIENCIA: {awareness}
DURACAO: {flow_days} dias
TOTAL DE EMAILS: {email_count}

IMPORTANTE: O fluxo deve ser especifico, com assuntos e CTAs reais (nao genericos).
Cada email deve ter tom e objetivo distintos para manter o lead engajado.

Retorne APENAS um JSON valido, sem markdown, sem texto antes ou depois:
{{
  "flow_name": "string",
  "strategy_summary": "string (2-3 linhas explicando a logica do fluxo)",
  "trigger": "string (evento que inicia o fluxo)",
  "steps": [
    {{
      "day": 0,
      "type": "email | condition | wait | action",
      "title": "string",
      "description": "string (o que acontece nessa etapa)",
      "subject": "string ou null (assunto real do email)",
      "body_angle": "string ou null (angulo/gancho do conteudo)",
      "cta": "string ou null (texto do botao de acao)"
    }}
  ],
  "final_action": "string (o que acontece ao final do fluxo)",
  "success_metrics": {{
    "expected_open_rate": "string",
    "expected_conversion_rate": "string",
    "estimated_roi": "string"
  }},
  "optimization_tips": [
    "string (dica de otimizacao 1)",
    "string (dica de otimizacao 2)"
  ]
}}"""

        result = await call_ai_json(prompt, system=SYSTEM_STRATEGIST, max_tokens=3000)
        return {"ok": True, "flow": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar fluxo: {str(e)}")


@router.post("/generate-email")
async def generate_email(data: dict):
    """
    Gera um email com variacao A/B para uso em campanhas ou fluxos.
    Body: tone, objective, theme, cta, target, context, client_name, product.
    """
    try:
        tone = data.get("tone") or "consultivo"
        objective = data.get("objective") or "gerar resposta"
        theme = data.get("theme") or "nutricao"
        cta = data.get("cta") or "responder o email"
        target = data.get("target") or "lead da base"
        context = data.get("context") or "nao informado"
        client_name = data.get("client_name") or ""
        product = data.get("product") or ""

        client_block = ""
        if client_name:
            client_block = f"Empresa: {client_name}" + (f" | Produto/Servico: {product}" if product else "")

        prompt = f"""Voce e um especialista em copywriting de alta conversao para email marketing B2B.
Crie um email completo com variacao A/B, com tom e estrutura distintos entre as versoes.

{f'Contexto do cliente: {client_block}' if client_block else ''}
Contexto da campanha: {context}
Tema: {theme}
Objetivo: {objective}
Tom de voz: {tone}
Publico-alvo: {target}
CTA principal: {cta}

IMPORTANTE:
- Os assuntos devem ser diferentes e usar tecnicas distintas (curiosidade vs. direto ao ponto)
- O corpo de cada versao deve ter estrutura diferente (storytelling vs. lista de beneficios)
- Nao use placeholders genericos como [NOME] sem contexto

Retorne APENAS um JSON valido, sem markdown, sem texto antes ou depois:
{{
  "version_a": {{
    "subject": "string (assunto com curiosidade/emocao)",
    "preheader": "string",
    "body": "string (HTML simples, com estrutura narrativa)",
    "cta_text": "string",
    "cta_url_placeholder": "string",
    "angle": "string (tecnica usada nessa versao)"
  }},
  "version_b": {{
    "subject": "string (assunto direto, orientado a beneficio)",
    "preheader": "string",
    "body": "string (HTML simples, com lista de beneficios)",
    "cta_text": "string",
    "cta_url_placeholder": "string",
    "angle": "string (tecnica usada nessa versao)"
  }},
  "recommended_version": "A ou B",
  "reasoning": "string (por que essa versao tende a performar melhor para esse publico)",
  "subject_test_tip": "string (dica para validar qual assunto performa melhor)"
}}"""

        result = await call_ai_json(prompt, system=SYSTEM_COPYWRITER, max_tokens=2500)
        return {"ok": True, "email": result}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro ao gerar email: {str(e)}")
