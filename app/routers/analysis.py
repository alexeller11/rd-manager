from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.ai_service import call_ai, build_client_context, SYSTEM_STRATEGIST, SYSTEM_SEO, SYSTEM_EXPERT
from app.routers.clients import fetch_client
from app.database import db_fetchval, db_fetchall

router = APIRouter()

ANALYSIS_GUIDES = {
    "complete": {
        "label": "Análise 360° de Marketing e Vendas",
        "system": SYSTEM_EXPERT,
        "guide": """Realize uma ANÁLISE 360° completa. Estruture assim:

## 1. Diagnóstico de Impacto
[Estado atual — o que os dados revelam sobre saúde do marketing]

## 2. Top 3 Problemas Críticos
[Os três maiores bloqueadores de crescimento agora, em ordem de urgência]

## 3. Plano de Ação Prioritário
[Para cada problema: ação concreta + métrica de sucesso + prazo]

## 4. Oportunidades Rápidas (Quick Wins)
[2-3 ações que podem gerar resultado em menos de 30 dias]

## 5. Sugestão de Copy/Mensagem Principal
[Uma mensagem central para usar em emails e landing pages]

## 6. Próximos 90 dias
[Roteiro de ações mês a mês]"""
    },
    "seo": {
        "label": "Auditoria SEO Técnico + AI SEO (AEO/GEO)",
        "system": SYSTEM_SEO,
        "guide": """Realize uma AUDITORIA SEO completa. Estruture assim:

## 1. Diagnóstico de Visibilidade
[Avaliação do SEO tradicional e presença em resultados de IA]

## 2. SEO Técnico — Checklist de Prioridades
[Velocidade, mobile, Core Web Vitals, indexação, URLs — com grau de urgência]

## 3. On-Page SEO
[Títulos, meta descriptions, headings, conteúdo — o que melhorar]

## 4. AI SEO (AEO/GEO)
[Como aparecer nas respostas de ChatGPT, Perplexity, Google AI Overviews]
- Schema markup recomendado
- Estrutura de conteúdo para extração por IAs
- Tom autoritativo vs. tom de vendas

## 5. Estratégia de Conteúdo para SEO
[Clusters de conteúdo, queries-alvo, formato ideal por intenção de busca]

## 6. Plano de Ação por Prioridade
[Quick wins vs. ações de longo prazo com estimativa de impacto]"""
    },
    "cro": {
        "label": "Análise de Conversão — CRO + Psicologia do Consumidor",
        "system": SYSTEM_STRATEGIST,
        "guide": """Realize uma ANÁLISE DE CRO completa baseada em Psicologia do Consumidor. Estruture assim:

## 1. Diagnóstico de Conversão
[Onde estão os maiores vazamentos no funil?]

## 2. Análise de Landing Pages
[Headline, proposta de valor, CTA, prova social, formulário — o que melhorar]

## 3. Psicologia por trás das fricções
[Quais gatilhos mentais estão sendo ignorados: urgência, escassez, autoridade, pertencimento]

## 4. Framework AIDA aplicado
[Attention, Interest, Desire, Action — onde o cliente perde o interesse]

## 5. A/B Tests Recomendados
[5 testes prioritários com hipótese, métricas e amostra mínima]

## 6. Plano de CRO por Etapa do Funil
[Topo, Meio e Fundo — ação específica para cada estágio]"""
    },
    "funnel": {
        "label": "Diagnóstico de Funil Completo (ToFu → BoFu)",
        "system": SYSTEM_STRATEGIST,
        "guide": """Realize um DIAGNÓSTICO DE FUNIL completo. Estruture assim:

## 1. Mapeamento do Funil Atual
[O que existe em cada etapa: Atração → Captura → Nutrição → Conversão → Retenção]

## 2. Gargalos por Etapa
[Onde o lead cai? Qual é a taxa de passagem estimada em cada estágio?]

## 3. Estratégia de Conteúdo por Estágio
- ToFu (Topo): atrair e educar
- MoFu (Meio): nutrir e qualificar
- BoFu (Fundo): converter e fechar

## 4. Automações Recomendadas no RD Station
[Fluxos específicos para cada etapa do funil]

## 5. Lead Scoring Sugerido
[Critérios de qualificação: perfil (fit) + comportamento (engajamento)]

## 6. KPIs do Funil
[Métricas para monitorar semana a semana]"""
    },
    "cold_metrics": {
        "label": "Análise de Métricas Frias — Leads Inativos e Reengajamento",
        "system": SYSTEM_EXPERT,
        "guide": """Realize uma ANÁLISE PROFUNDA de MÉTRICAS FRIAS. Estruture assim:

## 1. Diagnóstico de Leads Inativos
[Quantos leads não abrem há 60+ dias? Qual % da base? Tendência nos últimos 3 meses?]

## 2. Segmentação de Inativos
- Nunca abriram (dormentes desde captura)
- Abriram antes, mas pararam (desengajados)
- Abrem raramente (baixo engajamento crônico)
[Para cada: volume, causas prováveis, potencial de reativação]

## 3. Análise de Causas Raiz
[Por que esses leads ficaram inativos? Frequência excessiva? Conteúdo irrelevante? Falta de relevância?]

## 4. Impacto Financeiro
[Quanto de receita potencial está dormindo nessa base inativa?]

## 5. Estratégia de Reengajamento em 3 Fases

### Fase 1: Diagnóstico (Semana 1)
- Email com assunto provocador: "Sentimos sua falta..."
- Objetivo: medir quem ainda está vivo
- Segmentação: enviar apenas para 30% da base inativa

### Fase 2: Resgate (Semanas 2-3)
- Oferta especial ou conteúdo exclusivo
- Frequência: 2-3 emails com CTAs diferentes
- Segmentação: apenas quem abriu na Fase 1

### Fase 3: Limpeza (Semana 4)
- Último email: "Última chance antes de remover"
- Remover quem não engajar
- Manter apenas leads com potencial real

## 6. Automação de Reengajamento no RD Station
[Fluxo automático: gatilho → segmentação → sequência → limpeza]

## 7. Métricas de Sucesso
- Taxa de reabertura esperada: X%
- Taxa de conversão esperada: Y%
- Economia de custo de lista: Z%
- ROI do reengajamento

## 8. Ações Imediatas
[Top 3 ações para começar hoje]"""
    },
}


class AnalysisRequest(BaseModel):
    client_id: int
    type: str = "complete"


@router.post("/run")
async def run_analysis(req: AnalysisRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    config = ANALYSIS_GUIDES.get(req.type, ANALYSIS_GUIDES["complete"])
    context = build_client_context(client)

    prompt = f"""Atue como um Consultor de Marketing de Elite.

OBJETIVO: {config['label']}

CONTEXTO DO CLIENTE:
{context}

{config['guide']}"""

    result = await call_ai(prompt, system=config["system"], max_tokens=3500)

    # Persiste a análise no banco
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
    return rows


@router.get("/detail/{analysis_id}")
async def get_analysis_detail(analysis_id: int):
    from app.database import db_fetchone
    row = await db_fetchone("SELECT * FROM analyses WHERE id=$1", analysis_id)
    if not row:
        raise HTTPException(404, "Análise não encontrada")
    return row
