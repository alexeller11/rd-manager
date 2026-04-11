from fastapi import APIRouter
from app.ai_service import generate_text

router = APIRouter()


@router.post("/generate-flow")
async def generate_flow(data: dict):
    flow_days = int(data.get("flow_days") or 10)
    email_count = int(data.get("email_count") or 4)
    flow_type = data.get("flow_type") or "nutrição"
    goal = data.get("goal") or "conversão"

    prompt = f"""
Você é um Arquiteto de Automação de Marketing sênior especializado em RD Station.
O usuário quer um fluxo de automação estratégico de alto desempenho.

OBJETIVO PRINCIPAL: {goal}
TIPO DE FLUXO: {flow_type}
PRODUTO/SERVIÇO: {data.get("product")}
PÚBLICO-ALVO: {data.get("audience")}
NÍVEL DE CONSCIÊNCIA: {data.get("awareness")}
TEMPO TOTAL: {flow_days} dias
TOTAL DE EMAILS: {email_count}

REGRAS DE ESTRUTURA (PADRÃO RD STATION):
1. Defina um GATILHO (ex: Conversão em LP, Mudança de Estágio, Entrada em Segmentação).
2. Use blocos de ESPERA (ex: "Esperar 1 dia", "Esperar 4 horas").
3. Cada EMAIL deve ter: Dia, Assunto Sugerido, Objetivo Específico e CTA.
4. Adicione pelo menos uma CONDIÇÃO (ex: "Se abriu o email 2", "Se clicou no link Y").
5. Defina a AÇÃO FINAL (ex: "Marcar como Oportunidade", "Enviar para o CRM", "Mudar de Segmentação").

FORMATO DE RESPOSTA:
Retorne o plano no formato:
1. NOME E ESTRATÉGIA DO FLUXO (Breve resumo)
2. MAPA DO FLUXO (Linha do tempo passo a passo)
3. DETALHAMENTO DOS EMAILS (Assunto, Contexto e CTA)
4. MÉTRICAS DE SUCESSO ESPERADAS

Trabalhe com um tom consultivo e focado em ROI para a agência.
"""
    result = await generate_text(prompt)
    return {"flow": result}


@router.post("/generate-email")
async def generate_email(data: dict):
    tone = data.get("tone") or "consultivo"
    objective = data.get("objective") or "gerar resposta"
    theme = data.get("theme") or "nutrição"
    cta = data.get("cta") or "responder o email"
    target = data.get("target") or "lead da base"
    prompt = f"""
Crie um email completo de marketing.

Contexto:
{data.get("context")}

Tema: {theme}
Objetivo: {objective}
Tom de voz: {tone}
Público-alvo: {target}
CTA principal: {cta}

Entregue:
- assunto
- preheader
- corpo do email
- CTA
- versão A/B
"""
    result = await generate_text(prompt)
    return {"email": result}
