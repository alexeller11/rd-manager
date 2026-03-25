from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate-flow")
async def generate_flow(data: dict):
    prompt = f"""
    Crie um fluxo de email marketing profissional.

    Objetivo: {data.get("goal")}
    Produto: {data.get("product")}
    Público: {data.get("audience")}

    Retorne JSON com:
    - nome do fluxo
    - lista de emails
    - objetivo de cada email
    - motivo estratégico
    - timing (D+1, D+3...)
    """

    result = await generate_text(prompt)

    return {"flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    prompt = f"""
    Crie um email de marketing completo.

    Contexto:
    {data.get("context")}

    Inclua:
    - assunto
    - preheader
    - copy completa
    - CTA
    """

    result = await generate_text(prompt)

    return {"email": result}
