from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.ai_service import call_ai, build_client_context, SYSTEM_STRATEGIST, get_benchmarks
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


@router.post("/plan")
async def plan_campaign(req: CampaignRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    rd_data = parse_json_field(snap_row["data"]) if snap_row else {}
    client["rd_data"] = rd_data
    context = build_client_context(client)
    benchmarks = get_benchmarks(client.get("segment", "Outro"))

    prompt = f"""Crie um PLANO DE CAMPANHA completo e executável.

OBJETIVO: {req.objective}
DURAÇÃO: {req.duration}
CANAIS: {req.channels}
{f'ORÇAMENTO: {req.budget}' if req.budget else ''}
{f'INSTRUÇÕES EXTRAS: {req.extra}' if req.extra else ''}

DADOS DO CLIENTE:
{context}

BENCHMARKS DO SETOR ({client.get('segment','Outro')}):
- Taxa de abertura ideal: {benchmarks['open_rate']}%
- CTR ideal: {benchmarks['click_rate']}%
- Conversão ideal: {benchmarks['conversion']}%

## Visão Geral da Campanha
[Nome, conceito criativo e mensagem central]

## Público-Alvo
[Segmento específico, tamanho estimado, critério de seleção no RD Station]

## Cronograma de Execução
[Semana a semana — o que acontece, quando e por quem]

## Estratégia por Canal

### Email Marketing
[Sequência de emails: quantos, timing, assuntos, objetivos]

### Landing Page
[Headline, proposta de valor, CTA, elementos de conversão]

### Segmentação e Tags
[Como segmentar a base e tagear os leads ao longo da campanha]

## Configuração no RD Station
[Passo a passo: fluxos, automações, formulários, segmentações]

## KPIs e Metas
[Métricas específicas com metas numéricas baseadas nos benchmarks]

## Orçamento e ROI Esperado
[Estimativa de retorno baseada nas métricas históricas do cliente]

## Plano de Contingência
[O que fazer se a campanha não atingir 50% das metas na primeira semana]"""

    result = await call_ai(prompt, system=SYSTEM_STRATEGIST, max_tokens=3000)
    return {"result": result}
