from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate")
async def generate_insights(data: dict):
    prompt = f"""
    Analise os dados abaixo:

    {data}

    Gere insights estratégicos:

    - problemas
    - impactos
    - ações recomendadas

    Seja direto e prático.
    """

    result = await generate_text(prompt)

    return {"insights": result}
