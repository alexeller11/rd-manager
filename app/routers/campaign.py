from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.ai_service import SYSTEM_STRATEGIST, build_client_context, call_ai
from app.database import db_fetchone, parse_json_field
from app.routers.clients import fetch_client

router = APIRouter()


class CampaignRequest(BaseModel):
    client_id: int
    objective: str
    budget: Optional[str] = None
    duration: Optional[str] = "30 dias"
    channels: Optional[str] = "email, landing page"
    extra: Optional[str] = None


def get_benchmarks(segment: str = "Outro") -> dict:
    data = {
        "E-commerce": {"open_rate": 15.0, "click_rate": 2.1, "conversion": 1.5},
        "SaaS": {"open_rate": 21.0, "click_rate": 2.4, "conversion": 3.0},
        "Servicos": {"open_rate": 19.0, "click_rate": 2.5, "conversion": 5.0},
        "Educacao": {"open_rate": 24.0, "click_rate": 2.8, "conversion": 4.0},
        "Saude": {"open_rate": 22.0, "click_rate": 2.3, "conversion": 6.0},
        "Varejo": {"open_rate": 14.0, "click_rate": 1.9, "conversion": 1.2},
        "Industria": {"open_rate": 18.0, "click_rate": 2.2, "conversion": 2.5},
        "Outro": {"open_rate": 18.0, "click_rate": 2.0, "conversion": 2.0},
    }
    return data.get(segment, data["Outro"])


@router.post("/plan")
async def plan_campaign(req: CampaignRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id = $1 ORDER BY created_at DESC LIMIT 1",
        req.client_id,
    )
    rd_data = parse_json_field(snap_row["data"]) if snap_row else {}
    client["rd_data"] = rd_data

    context = build_client_context(client)
    benchmarks = get_benchmarks(client.get("segment", "Outro"))

    prompt = f"""
Crie um plano de campanha executável e realista.

OBJETIVO: {req.objective}
DURAÇÃO: {req.duration}
CANAIS: {req.channels}
ORÇAMENTO: {req.budget or "não informado"}
INSTRUÇÕES EXTRAS: {req.extra or "nenhuma"}

CONTEXTO DO CLIENTE:
{context}

BENCHMARKS DO SETOR:
- Abertura ideal: {benchmarks['open_rate']}%
- CTR ideal: {benchmarks['click_rate']}%
- Conversão ideal: {benchmarks['conversion']}%

Estruture a resposta em:
1. Visão geral
2. Público-alvo
3. Cronograma
4. Estratégia por canal
5. Configuração no RD Station
6. KPIs e metas
7. Contingência
"""

    result = await call_ai(
        prompt=prompt,
        system=SYSTEM_STRATEGIST,
        max_tokens=2500,
        temperature=0.3,
    )
    return {"result": result}
