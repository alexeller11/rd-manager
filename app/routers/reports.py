from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchall, parse_json_field
from app.auth_core import get_current_user
from app.ai_service import call_ai, build_client_context, SYSTEM_EXPERT
from app.routers.clients import fetch_client
from app.routers.health import calc_health_score

router = APIRouter()


class ReportRequest(BaseModel):
    client_id: int
    type: str = "monthly"
    period: Optional[str] = None
    extra: Optional[str] = None


@router.post("/generate")
async def generate_report(req: ReportRequest, user=Depends(get_current_user)):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    snap = parse_json_field(snap_row["data"]) if snap_row else {}

    crm_row = await db_fetchone(
        "SELECT data FROM crm_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    crm_data = parse_json_field(crm_row["data"]) if crm_row else {}

    health = calc_health_score(snap)
    context = build_client_context({**client, "rd_data": snap, "crm_data": crm_data})

    period_label = req.period or "último período"
    type_map = {
        "monthly":   "Relatório Mensal de Marketing",
        "executive": "Relatório Executivo (C-Level)",
        "campaign":  "Relatório de Campanha",
        "roi":       "Relatório de ROI e Performance",
    }
    report_type = type_map.get(req.type, "Relatório de Marketing")

    prompt = f"""Crie um {report_type} profissional para {period_label}.

CONTEXTO DO CLIENTE:
{context}

HEALTH SCORE: {health['score']}/100 ({health['label']})

{f'Instruções adicionais: {req.extra}' if req.extra else ''}

Estruture assim:

# {report_type} — {period_label}

## Sumário Executivo
[3-5 frases sobre o desempenho geral e principais destaques]

## KPIs do Período
[Tabela com métricas principais vs metas vs período anterior]

## Análise de Performance por Canal
[Email, Landing Pages, Segmentações — o que funcionou e o que não funcionou]

## Principais Conquistas
[Top 3 resultados positivos do período]

## Desafios e Problemas Identificados
[O que não performou e por quê]

## Insights Estratégicos
[Aprendizados que devem influenciar as próximas decisões]

## Recomendações para o Próximo Período
[5 ações prioritárias com impacto esperado]

## Conclusão
[Perspectiva geral e próximos passos]"""

    result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=3000)
    return {"result": result, "health": health}


@router.get("/history/{client_id}")
async def get_report_history(client_id: int, user=Depends(get_current_user)):
    # Reutiliza análises salvas como relatórios
    return await db_fetchall(
        "SELECT id, type, created_at FROM analyses WHERE client_id=$1 ORDER BY created_at DESC LIMIT 20",
        client_id
    )
