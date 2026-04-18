from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.ai_service import call_ai, build_client_context, build_rd_detail, SYSTEM_STRATEGIST, SYSTEM_SEO, SYSTEM_EXPERT
from app.routers.clients import fetch_client
from app.database import db_fetchval, db_fetchall, db_fetchone, parse_json_field
import json

router = APIRouter()


ANALYSIS_GUIDES = {
    "complete": {
        "label": "Análise 360° de Marketing e Vendas",
        "system": SYSTEM_EXPERT,
        "guide": """Realize uma ANÁLISE 360° completa baseada nos dados reais acima. Seja específico — cite nomes de campanhas, taxas reais, segmentações existentes.

## 1. Diagnóstico de Impacto
[Estado atual — o que os dados REAIS revelam sobre saúde do marketing. Cite métricas específicas.]

## 2. Top 3 Problemas Críticos
[Os três maiores bloqueadores de crescimento agora, baseados nos dados. Cite campanhas ou fluxos com problema.]

## 3. Plano de Ação Prioritário
[Para cada problema: ação concreta + métrica de sucesso + prazo]

## 4. Oportunidades Rápidas (Quick Wins)
[2-3 ações que podem gerar resultado em menos de 30 dias, baseadas nos dados existentes]

## 5. Sugestão de Copy/Mensagem Principal
[Uma mensagem central para usar em emails e landing pages, alinhada ao tom de voz do cliente]

## 6. Próximos 90 dias
[Roteiro de ações mês a mês]"""
    },
    "seo": {
        "label": "Auditoria SEO Técnico + AI SEO (AEO/GEO)",
        "system": SYSTEM_SEO,
        "guide": """Realize uma AUDITORIA SEO completa considerando as landing pages e dados reais acima.

## 1. Diagnóstico de Visibilidade
[Avaliação do SEO das landing pages existentes e presença em resultados de IA]

## 2. SEO Técnico — Checklist de Prioridades
[Velocidade, mobile, Core Web Vitals, indexação, URLs das LPs — com grau de urgência]

## 3. On-Page SEO
[Títulos, meta descriptions, headings, conteúdo das LPs — o que melhorar]

## 4. AI SEO (AEO/GEO)
[Como aparecer nas respostas de ChatGPT, Perplexity, Google AI Overviews]
- Schema markup recomendado para este segmento
- Estrutura de conteúdo para extração por IAs
- Tom autoritativo vs. tom de vendas

## 5. Estratégia de Conteúdo para SEO
[Clusters de conteúdo, queries-alvo, formato ideal por intenção de busca para este negócio]

## 6. Plano de Ação por Prioridade
[Quick wins vs. ações de longo prazo com estimativa de impacto]"""
    },
    "cro": {
        "label": "Análise de Conversão — CRO + Psicologia do Consumidor",
        "system": SYSTEM_STRATEGIST,
        "guide": """Realize uma ANÁLISE DE CRO completa usando os dados reais de conversão acima (campanhas, LPs, taxas).

## 1. Diagnóstico de Conversão
[Onde estão os maiores vazamentos no funil? Cite as taxas reais das campanhas e LPs.]

## 2. Análise de Landing Pages
[Para cada LP listada: headline provável, proposta de valor, CTA — o que melhorar com base na taxa de conversão]

## 3. Psicologia por trás das fricções
[Quais gatilhos mentais estão sendo ignorados: urgência, escassez, autoridade, pertencimento — específico para este segmento]

## 4. Framework AIDA aplicado
[Attention, Interest, Desire, Action — onde o lead perde o interesse com base nas taxas reais]

## 5. A/B Tests Recomendados
[5 testes prioritários com hipótese, métricas e amostra mínima — focados nas campanhas de menor performance]

## 6. Plano de CRO por Etapa do Funil
[Topo, Meio e Fundo — ação específica para cada estágio com base nos fluxos existentes]"""
    },
    "funnel": {
        "label": "Diagnóstico de Funil Completo (ToFu → BoFu)",
        "system": SYSTEM_STRATEGIST,
        "guide": """Realize um DIAGNÓSTICO DE FUNIL completo mapeando os ativos reais do cliente (automações, segmentações, LPs listadas acima).

## 1. Mapeamento do Funil Atual
[O que existe em cada etapa: cite as automações, segmentações e LPs reais do cliente]

## 2. Gargalos por Etapa
[Onde o lead cai? Calcule taxa de passagem com base nos dados reais de leads e conversões]

## 3. Estratégia de Conteúdo por Estágio
- ToFu (Topo): quais LPs e campanhas atuais servem aqui
- MoFu (Meio): quais automações nutrem — o que está faltando
- BoFu (Fundo): quais segmentações convertem — onde melhorar

## 4. Automações Recomendadas no RD Station
[Fluxos específicos faltantes com base no que já existe]

## 5. Lead Scoring Sugerido
[Critérios de qualificação: perfil (fit) + comportamento (engajamento) baseado nas segmentações existentes]

## 6. KPIs do Funil
[Métricas para monitorar semana a semana, com benchmarks para este segmento]"""
    },
    "cold_metrics": {
        "label": "Análise de Métricas Frias — Leads Inativos e Reengajamento",
        "system": SYSTEM_EXPERT,
        "guide": """Realize uma ANÁLISE PROFUNDA de MÉTRICAS FRIAS usando os dados reais acima.

## 1. Diagnóstico de Leads Inativos
[Com base no total de leads vs. taxas de abertura reais: quantos estão inativos? Qual % da base?]

## 2. Segmentação de Inativos
- Nunca abriram (dormentes desde captura)
- Abriram antes, mas pararam (desengajados — cite campanhas com queda)
- Abrem raramente (baixo engajamento crônico)
[Para cada: volume estimado, causas prováveis, potencial de reativação]

## 3. Análise de Causas Raiz
[Por que esses leads ficaram inativos? Analise frequência das campanhas listadas, relevância por segmentação]

## 4. Impacto Financeiro
[Quanto de receita potencial está dormindo nessa base inativa?]

## 5. Estratégia de Reengajamento em 3 Fases

### Fase 1: Diagnóstico (Semana 1)
- Email com assunto provocador baseado no tom de voz do cliente
- Objetivo: medir quem ainda está vivo
- Segmentação: usar as segmentações existentes como base

### Fase 2: Resgate (Semanas 2-3)
- Oferta especial ou conteúdo exclusivo alinhado ao segmento
- Frequência: 2-3 emails com CTAs diferentes
- Segmentação: apenas quem abriu na Fase 1

### Fase 3: Limpeza (Semana 4)
- Último email: \"Última chance antes de remover\"
- Remover quem não engajar
- Manter apenas leads com potencial real

## 6. Automação de Reengajamento no RD Station
[Fluxo automático aproveitando as automações existentes como base: gatilho → segmentação → sequência → limpeza]

## 7. Métricas de Sucesso
- Taxa de reabertura esperada vs. atual ({avg_open_rate}% atual)
- Taxa de conversão esperada
- Economia de custo de lista
- ROI do reengajamento

## 8. Ações Imediatas
[Top 3 ações para começar hoje com os recursos que já existem]"""
    },
}


async def _enrich_rd_data_from_db(client_id: int, rd_data: dict) -> dict:
    """
    Enriquece rd_data com dados reais sincronizados no banco (rd_objects),
    sobrescrevendo/completando campanhas, segmentações, automações e LPs
    que podem não estar no snapshot.
    """
    rd = dict(rd_data) if rd_data else {}

    # Campanhas
    rows_campaigns = await db_fetchall(
        """SELECT payload FROM rd_objects
           WHERE client_id=$1 AND object_type='campaigns'
           ORDER BY synced_at DESC LIMIT 15""",
        client_id
    )
    if rows_campaigns:
        campaigns = []
        for row in rows_campaigns:
            p = parse_json_field(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
            campaigns.append({
                "name": p.get("name") or p.get("subject") or p.get("title") or "Sem nome",
                "sent": p.get("emails_sent") or p.get("sent") or 0,
                "open_rate": float(p.get("open_rate") or p.get("opens_rate") or 0),
                "click_rate": float(p.get("click_rate") or p.get("clicks_rate") or 0),
                "status": p.get("status") or p.get("state") or "?",
            })
        rd["recent_campaigns"] = campaigns

    # Segmentações
    rows_segs = await db_fetchall(
        """SELECT payload FROM rd_objects
           WHERE client_id=$1 AND object_type='segmentations'
           ORDER BY synced_at DESC LIMIT 15""",
        client_id
    )
    if rows_segs:
        segs = []
        for row in rows_segs:
            p = parse_json_field(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
            segs.append({
                "name": p.get("name") or p.get("title") or "Sem nome",
                "contacts_count": p.get("contacts_count") or p.get("contacts") or p.get("leads") or 0,
            })
        rd["segmentations"] = segs

    # Automações / Workflows
    rows_flows = await db_fetchall(
        """SELECT payload FROM rd_objects
           WHERE client_id=$1 AND object_type='workflows'
           ORDER BY synced_at DESC LIMIT 15""",
        client_id
    )
    if rows_flows:
        automations = []
        for row in rows_flows:
            p = parse_json_field(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
            automations.append({
                "name": p.get("name") or p.get("title") or "Sem nome",
                "status": p.get("status") or p.get("workflow_status") or p.get("state") or "?",
                "leads_count": p.get("leads_count") or p.get("contacts_count") or 0,
            })
        rd["automations"] = automations

    # Landing Pages
    rows_lps = await db_fetchall(
        """SELECT payload FROM rd_objects
           WHERE client_id=$1 AND object_type='landing_pages'
           ORDER BY synced_at DESC LIMIT 10""",
        client_id
    )
    if rows_lps:
        lps = []
        for row in rows_lps:
            p = parse_json_field(row["payload"]) if isinstance(row["payload"], str) else (row["payload"] or {})
            cr = p.get("conversion_rate") or 0
            lps.append({
                "name": p.get("title") or p.get("name") or "Sem nome",
                "visits": p.get("visits_count") or p.get("visitors_count") or 0,
                "conversions": p.get("conversions_count") or p.get("conversions") or 0,
                "conversion_rate": float(cr) * 100 if float(cr) <= 1 else float(cr),
            })
        rd["landing_pages"] = lps

    return rd


class AnalysisRequest(BaseModel):
    client_id: int
    type: str = "complete"


@router.post("/run")
async def run_analysis(req: AnalysisRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    # Snapshot mais recente
    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1",
        req.client_id
    )
    rd_data = {}
    if snap_row:
        rd_data = parse_json_field(snap_row["data"]) or {}

    # Enriquece com dados reais do banco (rd_objects sincronizados)
    rd_data = await _enrich_rd_data_from_db(req.client_id, rd_data)
    client["rd_data"] = rd_data

    config = ANALYSIS_GUIDES.get(req.type, ANALYSIS_GUIDES["complete"])

    context = build_client_context(client)

    # Substitui placeholder de open_rate no guia cold_metrics
    guide_text = config["guide"]
    avg_open = rd_data.get("avg_open_rate", "N/A")
    guide_text = guide_text.replace("{avg_open_rate}", str(avg_open))

    prompt = f"""Atue como um Consultor de Marketing de Elite.

OBJETIVO: {config['label']}

CONTEXTO DO CLIENTE:
{context}

INSTRUÇÕES:
{guide_text}"""

    result = await call_ai(prompt, system=config["system"], max_tokens=3500)

    analysis_id = await db_fetchval(
        "INSERT INTO analyses (client_id, type, prompt, result) VALUES ($1,$2,$3,$4) RETURNING id",
        req.client_id, req.type, prompt[:1000], result
    )

    return {"result": result, "analysis_id": analysis_id}


@router.get("/history/{client_id}")
async def get_analysis_history(client_id: int):
    rows = await db_fetchall(
        "SELECT id, type, created_at FROM analyses WHERE client_id=$1 ORDER BY created_at DESC LIMIT 20",
        client_id
    )
    return [
        {"id": r["id"], "type": r["type"], "created_at": str(r["created_at"])}
        for r in (rows or [])
    ]


@router.get("/detail/{analysis_id}")
async def get_analysis_detail(analysis_id: int):
    row = await db_fetchone("SELECT * FROM analyses WHERE id=$1", analysis_id)
    if not row:
        raise HTTPException(404, "Análise não encontrada")
    d = dict(row)
    for field in ("created_at", "updated_at"):
        if field in d and d[field] is not None:
            d[field] = str(d[field])
    return d
