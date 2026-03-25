from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate-flow")
async def generate_flow(data: dict):
    prompt = f"""
    Crie um fluxo de email marketing profissional.

    Contexto:
    Objetivo: {data.get("goal")}
    Produto: {data.get("product")}
    Público: {data.get("audience")}
    Nível de consciência: {data.get("awareness")}

    Retorne JSON estruturado:

    {{
      "flow_name": "...",
      "emails": [
        {{
          "step": 1,
          "name": "...",
          "timing": "D+1",
          "objective": "...",
          "reason": "...",
          "cta": "..."
        }}
      ]
    }}
    """

    result = await generate_text(prompt)

    return {"flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    prompt = f"""
    Crie um email de marketing completo.

    Contexto:
    {data.get("context")}

    Estrutura obrigatória:
    - Assunto
    - Preheader
    - Corpo do email
    - CTA
    - Versão alternativa A/B

    Seja persuasivo e natural.
    """

    result = await generate_text(prompt)

    return {"email": result}
