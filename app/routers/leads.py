from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze")
async def analyze_leads(data: dict):
    prompt = f"""
    Analise essa base de leads:

    {data}

    Retorne:
    - segmentos
    - problemas
    - oportunidades
    - ações recomendadas
    """

    result = await generate_text(prompt)

    return {"analysis": result}
