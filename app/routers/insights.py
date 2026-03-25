from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate")
async def generate_insights(data: dict):
    prompt = f"""
Transforme estes dados em insights estratégicos.

Dados:
{data}

Entregue:
- o que está acontecendo
- por que importa
- o que fazer agora
- prioridade
"""
    result = await generate_text(prompt)
    return {"insights": result}
