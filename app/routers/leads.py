from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze-base")
async def analyze_leads(data: dict):
    prompt = f"""
    Analise essa base de leads:

    {data}

    Retorne:

    {{
      "segments": [
        {{
          "name": "...",
          "description": "...",
          "size": "...",
          "action": "..."
        }}
      ],
      "insights": [],
      "opportunities": [],
      "recommended_actions": []
    }}
    """

    result = await generate_text(prompt)

    return {"analysis": result}


@router.post("/segment")
async def segment_leads(data: dict):
    prompt = f"""
    Crie segmentações inteligentes para essa base:

    {data}

    Retorne lista de segmentos acionáveis.
    """

    result = await generate_text(prompt)

    return {"segments": result}
