import json
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchall, db_fetchval, db_execute, parse_json_field
from app.ai_service import call_ai, build_client_context, SYSTEM_EXPERT
from app.routers.clients import fetch_client
from app.routers.health import calc_health_score

router = APIRouter()


async def _get_snap(client_id: int) -> dict:
    row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    return parse_json_field(row["data"]) if row else {}


# ─── Análise semanal ─────────────────────────────────────────────────────────

async def run_weekly_analysis_job(client_id: int):
    try:
        client = await fetch_client(client_id)
        if not client:
            return
        snap = await _get_snap(client_id)
        client["rd_data"] = snap
        context = build_client_context(client)

        prompt = f"""Realize uma ANÁLISE SEMANAL EXECUTIVA de marketing digital. Seja direto e focado em dados.

DADOS DO CLIENTE:
{context}

Estruture exatamente assim:

## Resumo da semana
[2-3 frases sobre o estado geral]

## 3 Insights mais importantes
1. [Insight com dado específico]
2. [Insight com dado específico]
3. [Insight com dado específico]

## Alerta principal
[O problema mais urgente que precisa de atenção agora]

## Ação prioritária desta semana
[Uma única ação concreta e mensurável para implementar]

## Projeção para próxima semana
[O que esperar se a ação for implementada]"""

        result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=1000)
        week_ref = datetime.now().strftime("%Y-W%W")
        await db_fetchval(
            "INSERT INTO weekly_analyses (client_id, result, week_ref) VALUES ($1,$2,$3) RETURNING id",
            client_id, result, week_ref
        )
    except Exception as e:
        print(f"Erro análise semanal cliente {client_id}: {e}")


class WeeklyRequest(BaseModel):
    client_id: int


@router.post("/weekly/run/{client_id}")
async def trigger_weekly(client_id: int, background_tasks: BackgroundTasks):
    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    background_tasks.add_task(run_weekly_analysis_job, client_id)
    return {"message": "Análise semanal iniciada. Disponível em instantes."}


@router.post("/weekly/run-all")
async def run_all_weekly(background_tasks: BackgroundTasks):
    clients = await db_fetchall("SELECT id FROM clients")
    for c in clients:
        background_tasks.add_task(run_weekly_analysis_job, c["id"])
    return {"message": f"Análise iniciada para {len(clients)} clientes."}


@router.get("/weekly/latest/{client_id}")
async def get_latest_weekly(client_id: int):
    row = await db_fetchone(
        "SELECT result, week_ref, created_at FROM weekly_analyses WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1",
        client_id
    )
    if not row:
        return {"result": None, "week_ref": None, "created_at": None}
    return {"result": row["result"], "week_ref": row["week_ref"], "created_at": str(row["created_at"])}


@router.get("/weekly/history/{client_id}")
async def get_weekly_history(client_id: int):
    return await db_fetchall(
        "SELECT id, week_ref, created_at FROM weekly_analyses WHERE client_id=$1 ORDER BY created_at DESC LIMIT 12",
        client_id
    )


# ─── A/B Test Advisor ────────────────────────────────────────────────────────

class ABTestRequest(BaseModel):
    client_id: int
    element: str
    context: str = ""


@router.post("/abtest/generate")
async def generate_ab_test(req: ABTestRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    context = build_client_context(client)
    labels = {
        "subject": "linha de assunto do email",
        "cta": "call-to-action (botão/link)",
        "content": "conteúdo e abordagem do email",
        "send_time": "horário e dia de envio",
        "sender_name": "nome do remetente",
    }
    label = labels.get(req.element, req.element)
    prompt = f"""Crie um PLANO DE A/B TEST completo para testar a {label}.

DADOS DO CLIENTE:
{context}
{f'Contexto adicional: {req.context}' if req.context else ''}

## Hipótese
[O que você está testando e por que]

## Versão A (Controle)
[Versão atual ou mais conservadora — com exemplo concreto]

## Versão B (Variante)
[Versão nova ou mais ousada — com exemplo concreto]

## Métricas para acompanhar
- Métrica principal: [qual e como medir]
- Métricas secundárias: [lista]

## Tamanho da amostra recomendado
[Quantos contatos em cada versão e por quê]

## Duração do teste
[Quanto tempo rodar e por quê]

## Como configurar no RD Station
[Passos práticos]

## Como interpretar os resultados
[Critério para declarar vencedor]"""

    result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=1200)
    return {"result": result}


# ─── Calendário Editorial ─────────────────────────────────────────────────────

class CalendarRequest(BaseModel):
    client_id: int
    month: Optional[str] = None
    focus: Optional[str] = None


@router.post("/calendar/generate")
async def generate_calendar(req: CalendarRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    context = build_client_context(client)
    month = req.month or datetime.now().strftime("%B %Y")

    prompt = f"""Crie um CALENDÁRIO EDITORIAL COMPLETO de email marketing para {month}.

DADOS DO CLIENTE:
{context}
{f'Foco especial: {req.focus}' if req.focus else ''}

Crie um calendário com 8 a 12 envios. Para cada envio:
**Data | Tipo | Assunto | Objetivo | Segmento**

## Lógica do mês
[Narrativa que conecta todos os envios]

## Datas estratégicas
[Feriados e sazonalidades relevantes para este negócio]

## Cadência recomendada
[Frequência ideal e justificativa]

## Como configurar no RD Station
[Passos para agendar os envios]"""

    result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=1500)
    return {"result": result, "month": month}


# ─── Radar de Concorrência ───────────────────────────────────────────────────

class CompetitorRequest(BaseModel):
    client_id: int
    competitors: Optional[str] = None


@router.post("/competitor/analyze")
async def analyze_competitors(req: CompetitorRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    context = build_client_context(client)

    prompt = f"""Realize uma ANÁLISE DE CONCORRÊNCIA estratégica.

DADOS DO CLIENTE:
{context}
{f'Concorrentes mencionados: {req.competitors}' if req.competitors else ''}

## Perfil dos principais concorrentes
[Para cada: posicionamento, pontos fortes, fracos]

## Diferenciais competitivos do cliente
[O que o cliente tem que os concorrentes não têm]

## Gaps de mercado
[Oportunidades não exploradas por nenhum player]

## Estratégia de email marketing dos concorrentes
[Como provavelmente comunicam, que temas usam]

## Como se diferenciar na comunicação
[Posicionamento de mensagem único]

## Ações de inteligência competitiva
[O que monitorar semanalmente e como]

## Oportunidades de captura de mercado
[Top 3 ações concretas para ganhar fatia dos concorrentes]"""

    result = await call_ai(prompt, system=SYSTEM_EXPERT, max_tokens=1500)
    return {"result": result}


# ─── Dashboard público ───────────────────────────────────────────────────────

@router.get("/public/{client_id}")
async def get_public_dashboard(client_id: int):
    client = await db_fetchone("SELECT name, segment, website FROM clients WHERE id=$1", client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    snap = parse_json_field(snap_row["data"]) if snap_row else {}
    weekly = await db_fetchone(
        "SELECT result, week_ref FROM weekly_analyses WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", client_id
    )
    health = calc_health_score(snap)
    return {
        "client": {"name": client["name"], "segment": client["segment"]},
        "health": health,
        "metrics": {
            "total_leads":    snap.get("total_leads"),
            "avg_open_rate":  snap.get("avg_open_rate"),
            "avg_click_rate": snap.get("avg_click_rate"),
            "segments_count": len(snap.get("segmentations", [])),
        },
        "weekly_insight": weekly["result"] if weekly else "",
        "week_ref": weekly["week_ref"] if weekly else "",
        "generated_at": datetime.now().isoformat(),
    }
