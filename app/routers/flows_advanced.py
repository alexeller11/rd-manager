from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate-flow")
async def generate_flow(data: dict):
    flow_days = int(data.get("flow_days") or 10)
    email_count = int(data.get("email_count") or 4)
    flow_type = data.get("flow_type") or "nutrição"
    prompt = f"""
Crie um fluxo de email marketing profissional para agência.

Objetivo: {data.get("goal")}
Produto: {data.get("product")}
Público: {data.get("audience")}
Nível de consciência: {data.get("awareness")}
Tipo de fluxo: {flow_type}
Total de dias do fluxo: {flow_days}
Quantidade de emails no fluxo: {email_count}

Retorne:
- nome do fluxo
- objetivo do fluxo
- mapa visual do fluxo em etapas (dia, gatilho, ação, objetivo)
- lista de emails em ordem, com:
  - dia de envio
  - objetivo do email
  - tema central
  - CTA recomendado
  - variável de personalização sugerida
- lógica estratégica da sequência

Responda em português e de forma operacional.
"""
    result = await generate_text(prompt)
    return {"flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    tone = data.get("tone") or "consultivo"
    objective = data.get("objective") or "gerar resposta"
    theme = data.get("theme") or "nutrição"
    cta = data.get("cta") or "responder o email"
    target = data.get("target") or "lead da base"
    prompt = f"""
Crie um email completo de marketing.

Contexto:
{data.get("context")}

Tema: {theme}
Objetivo: {objective}
Tom de voz: {tone}
Público-alvo: {target}
CTA principal: {cta}

Entregue:
- assunto
- preheader
- corpo do email
- CTA
- versão A/B
"""
    result = await generate_text(prompt)
    return {"email": result}
