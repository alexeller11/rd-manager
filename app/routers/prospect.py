from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze-business")
async def analyze_business(data: dict):
    prompt = f"""
Analise este negócio para prospecção comercial de agência.

Nicho: {data.get("niche")}
Cidade: {data.get("city")}
Site: {data.get("site")}

Entregue:
- problemas percebidos
- oportunidades
- argumento comercial
- abordagem pronta
"""
    result = await generate_text(prompt)
    return {"analysis": result}
