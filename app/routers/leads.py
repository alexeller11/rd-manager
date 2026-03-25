from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze-base")
async def analyze_leads(data: dict):
    prompt = f"""
Analise esta base de leads como uma agência estratégica.

Dados:
{data}

Entregue:
- segmentos identificados
- oportunidades
- gargalos
- ações recomendadas
- campanhas sugeridas
- leads que merecem reativação
"""
    result = await generate_text(prompt)
    return {"analysis": result}


@router.post("/segment")
async def segment_leads(data: dict):
    prompt = f"""
Crie segmentações úteis e acionáveis para esta base.

Dados:
{data}

Entregue uma segmentação que faça sentido para operação de marketing.
"""
    result = await generate_text(prompt)
    return {"segments": result}
