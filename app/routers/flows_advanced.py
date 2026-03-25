from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate-flow")
async def generate_flow(data: dict):
    prompt = f"""
Crie um fluxo de email marketing profissional para agência.

Objetivo: {data.get("goal")}
Produto: {data.get("product")}
Público: {data.get("audience")}
Nível de consciência: {data.get("awareness")}

Retorne:
- nome do fluxo
- lista de emails
- timing
- motivo estratégico
- CTA ideal
- ordem da sequência
"""
    result = await generate_text(prompt)
    return {"flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    prompt = f"""
Crie um email completo de marketing.

Contexto:
{data.get("context")}

Entregue:
- assunto
- preheader
- corpo do email
- CTA
- versão A/B
"""
    result = await generate_text(prompt)
    return {"email": result}
