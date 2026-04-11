import json
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from app.database import db_fetchone, db_fetchall, db_fetchval, parse_json_field
from app.ai_service import call_ai, build_client_context, SYSTEM_COPYWRITER, SYSTEM_STRATEGIST
from app.routers.clients import fetch_client

router = APIRouter()


class EmailRequest(BaseModel):
    client_id: int
    type: str
    tone: Optional[str] = "Conversacional e direto"
    theme: Optional[str] = None
    objective: Optional[str] = None
    duration: Optional[str] = None
    extra: Optional[str] = None
    framework: Optional[str] = "AIDA"


EMAIL_TYPES = {
    "nurturing":    {"label": "nutrição de leads", "goal": "educar o lead e aproximar da decisão de compra", "framework": "AIDA ou PAS", "tip": "Entregue valor antes de pedir qualquer ação. CTA de próximo passo, não de compra."},
    "welcome":      {"label": "boas-vindas", "goal": "fazer o lead se sentir especial e definir o que vem a seguir", "framework": "Storytelling ou Antes/Depois/Ponte", "tip": "Maior taxa de abertura de todos os emails. Comece agradecendo, apresente a promessa da marca, diga o que o lead pode esperar."},
    "promo":        {"label": "promocional", "goal": "gerar compra imediata com urgência real", "framework": "4Ps (Promise, Picture, Proof, Push)", "tip": "Urgência real, não falsa. Benefício antes do preço. Prova social ou garantia para quebrar objeção."},
    "reengagement": {"label": "reengajamento de inativos", "goal": "reativar leads que não abrem há 60+ dias", "framework": "PAS (Problema-Agitação-Solução)", "tip": "Reconheça o silêncio de forma leve. Oferta ou conteúdo exclusivo. Se não abrir, remova da lista."},
    "followup":     {"label": "follow-up", "goal": "continuar conversa após uma ação do lead", "framework": "AIDA", "tip": "Referencie a ação anterior. Seja breve. Um único próximo passo."},
    "launch":       {"label": "lançamento", "goal": "gerar expectativa, desejo e conversão", "framework": "Sequência: Antecipação > Abertura > Urgência > Último dia", "tip": "Lance em 3-5 emails. Construa antecipação antes de revelar o produto."},
    "newsletter":   {"label": "newsletter e conteúdo", "goal": "entregar valor e manter relacionamento", "framework": "Editorial: tema > insight > ação", "tip": "Um único tema. Começa com dado surpreendente. Termina com pergunta para aumentar engajamento."},
    "strategy":     {"label": "estratégia completa", "goal": "sequência de emails do início ao fim", "framework": "Sequência de nutrição completa", "tip": "Crie 5-10 emails encadeados com lógica de funil."},
}


@router.post("/generate")
async def generate_email(req: EmailRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")

    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    rd_data = parse_json_field(snap_row["data"]) if snap_row else {}
    client["rd_data"] = rd_data
    context = build_client_context(client)
    benchmarks = {"open_rate": 20, "click_rate": 2}

    if req.type == "strategy":
        return await _generate_strategy(req, client, context, benchmarks)

    type_info = EMAIL_TYPES.get(req.type, EMAIL_TYPES["nurturing"])
    current_open = rd_data.get("avg_open_rate", 0)
    open_bench   = benchmarks["open_rate"]
    perf_note = ""
    if current_open and current_open < open_bench:
        perf_note = f"\nATENÇÃO: Taxa de abertura atual ({current_open}%) abaixo do benchmark ({open_bench}%). Assuntos precisam ser especialmente poderosos."
    elif current_open and current_open >= open_bench:
        perf_note = f"\nNOTA: Taxa de {current_open}% acima do benchmark ({open_bench}%). Mantenha o padrão de qualidade."

    prompt = f"""Escreva um email de {type_info['label']} de alta conversão.

OBJETIVO: {type_info['goal']}
FRAMEWORK: {type_info['framework']}
TOM DE VOZ: {req.tone}
TEMA: {req.theme or 'defina o melhor tema baseado no contexto'}
{f'INSTRUÇÕES ADICIONAIS: {req.extra}' if req.extra else ''}
DICA DE COPYWRITING: {type_info['tip']}
{perf_note}

DADOS DA EMPRESA:
{context}

ESTRUTURA OBRIGATÓRIA:

## ASSUNTOS (3 opções para A/B test)
**Opção A — Curiosidade/Gap:** [cria curiosidade sem entregar tudo]
**Opção B — Dor/Benefício:** [toca na dor ou promete benefício claro]
**Opção C — Número/Especificidade:** [usa número, prazo ou dado específico]

## PRÉ-HEADER
[complementa o assunto, max 90 caracteres]

---

## CORPO DO EMAIL

**Saudação:** Oi {{primeiro_nome}},

**Abertura (max 3 linhas — o leitor decide aqui):**
[gancho: história, dado surpreendente, pergunta, afirmação ousada]

**Desenvolvimento:**
[argumento com o framework — parágrafos curtos de 2-3 linhas]

**Prova social ou credibilidade:**
[depoimento, dado, caso de uso ou garantia]

**CTA principal:**
[texto do botão deve dizer o que acontece ao clicar]

**Assinatura:**
[Nome | Cargo | Empresa]

**PS:**
[Uma linha que resume o benefício ou cria urgência]

---

## NOTAS DE PERSONALIZAÇÃO PARA RD STATION
[variáveis de personalização e segmento ideal]

## POR QUE ESTE EMAIL VAI FUNCIONAR
[2-3 razões técnicas de copywriting]"""

    result = await call_ai(prompt, system=SYSTEM_COPYWRITER, max_tokens=2000)

    await db_fetchval(
        "INSERT INTO email_strategies (client_id, type, subject, body) VALUES ($1,$2,$3,$4) RETURNING id",
        req.client_id, req.type, req.theme or "", result
    )
    return {"result": result}


async def _generate_strategy(req, client, context, benchmarks):
    tipo = req.theme or "Fluxo de nutrição completo"
    duracao = req.duration or "5 emails"
    objetivo = req.objective or "converter leads em clientes"

    prompt = f"""Crie uma ESTRATÉGIA COMPLETA DE EMAIL MARKETING do tipo "{tipo}" com {duracao}.

OBJETIVO: {objetivo}
TOM DE VOZ: {req.tone}
{f'INSTRUÇÕES: {req.extra}' if req.extra else ''}

DADOS DA EMPRESA:
{context}

BENCHMARKS DO SETOR ({client.get('segment','Outro')}):
- Taxa de abertura ideal: {benchmarks['open_rate']}%+
- CTR ideal: {benchmarks['click_rate']}%+

Para CADA EMAIL da sequência entregue:

### Email [N] — [Nome do email]
**Intervalo:** D+[X] após o anterior
**Objetivo:** [o que este email específico deve fazer]
**Framework:** [AIDA / PAS / 4Ps / Storytelling]
**Assunto principal:** [assunto poderoso]
**Assunto variante (A/B):** [opção para testar]
**Pré-header:** [complemento do assunto]
**Abertura:** [primeiras 2 linhas — o gancho]
**Argumento central:** [o que desenvolver no corpo]
**CTA:** [texto exato do botão e para onde vai]
**PS:** [uma linha de PS poderoso]
**Segmento:** [para quem enviar especificamente]

---

## LÓGICA DA SEQUÊNCIA
[Como os emails se conectam e por que nessa ordem]

## GATILHOS DE SAÍDA
[Que comportamento tira o lead da sequência]

## COMO CONFIGURAR NO RD STATION
[Passo a passo da automação]

## MÉTRICAS DE SUCESSO
[O que monitorar semana a semana]"""

    result = await call_ai(prompt, system=SYSTEM_COPYWRITER, max_tokens=2500)
    return {"result": result}


@router.post("/segmentation")
async def generate_segmentation(req: EmailRequest):
    client = await fetch_client(req.client_id)
    if not client:
        raise HTTPException(404, "Cliente não encontrado")
    snap_row = await db_fetchone(
        "SELECT data FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1", req.client_id
    )
    rd_data = parse_json_field(snap_row["data"]) if snap_row else {}
    client["rd_data"] = rd_data
    context = build_client_context(client)
    benchmarks = {"open_rate": 20, "click_rate": 2}
    segs_info = ""
    if rd_data.get("segmentations"):
        segs_info = "\n\nSEGMENTAÇÕES JA EXISTENTES:\n" + "\n".join(
            [f"- {s['name']}: {s.get('contacts', 0)} contatos" for s in rd_data["segmentations"]]
        )
    prompt = f"""Crie uma ESTRATÉGIA DE SEGMENTAÇÃO para: "{req.objective or req.theme or 'otimização geral'}"

DADOS DA EMPRESA:
{context}{segs_info}

BENCHMARKS ({client.get('segment','Outro')}): abertura ideal {benchmarks['open_rate']}%, CTR ideal {benchmarks['click_rate']}%

Para cada segmento:
### Segmento [N]: [Nome descritivo]
**Critério de entrada:** [regra exata no RD Station]
**Tamanho estimado:** [% da base]
**Mensagem principal:** [ângulo específico]
**Melhor tipo de email:** [qual tipo funciona]
**CTA ideal:** [o que pedir]
**Frequência recomendada:** [emails/mês]

## PRIORIZAÇÃO
[Qual segmento atacar primeiro e por quê]

## COMO CRIAR NO RD STATION
[Campos e filtros específicos]

## AUTOMAÇÃO SUGERIDA
[Qual segmento se beneficia de automação]"""

    result = await call_ai(prompt, system=SYSTEM_STRATEGIST, max_tokens=2000)
    return {"result": result}


@router.get("/history/{client_id}")
async def get_email_history(client_id: int):
    return await db_fetchall(
        "SELECT id, type, subject, created_at FROM email_strategies WHERE client_id=$1 ORDER BY created_at DESC LIMIT 30",
        client_id
    )


@router.get("/detail/{email_id}")
async def get_email_detail(email_id: int):
    row = await db_fetchone("SELECT * FROM email_strategies WHERE id=$1", email_id)
    return row or {}
