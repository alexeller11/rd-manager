from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze-business")
async def analyze_business(data: dict):
    prompt = f"""
    Analise esse negócio:

    Nicho: {data.get("niche")}
    Cidade: {data.get("city")}
    Site: {data.get("site")}

    Retorne:

    - problemas de marketing
    - oportunidades
    - abordagem comercial pronta
    """

    result = await generate_text(prompt)

    return {"analysis": result}
