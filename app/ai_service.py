"""
Serviço de IA — Groq/Llama com prompts enriquecidos.
Incorpora frameworks de marketing dos arquivos marketingskills e claude-seo.
"""
import os
import httpx
import json

GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


async def call_ai(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """Chama a API do Groq ou OpenAI. Retorna string de erro em caso de falha."""
    api_key = GROQ_API_KEY
    url = GROQ_URL
    model = GROQ_MODEL

    # Fallback para OpenAI se Groq não estiver configurado
    if not api_key and OPENAI_API_KEY:
        api_key = OPENAI_API_KEY
        url = OPENAI_URL
        model = "gpt-4o"

    if not api_key:
        return "Erro: Nenhuma chave de API (GROQ ou OPENAI) configurada. Adicione nas variáveis de ambiente do Railway."

    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    payload = {
        "model": GROQ_MODEL,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.75,
    }

    try:
        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post(
                GROQ_URL,
                headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                json=payload,
            )
            resp.raise_for_status()
            return resp.json()["choices"][0]["message"]["content"]
    except httpx.HTTPStatusError as e:
        return f"Erro na API de IA (HTTP {e.response.status_code}): {e.response.text[:200]}"
    except Exception as e:
        return f"Erro na análise de IA: {str(e)}"


# ─── Personas de IA ──────────────────────────────────────────────────────────

SYSTEM_EXPERT = """Você é um Consultor de Marketing Estratégico de alto nível com visão de negócios e foco no fator humano.

Como você atua:
- Use linguagem natural, empática e persuasiva. Escreva como se estivesse numa consultoria presencial.
- Foco profundo na estratégia: explique o que os números representam no comportamento do consumidor.
- Traga insights criativos e fuja de clichês. Seja consultivo e provoque reflexões.
- Use frameworks como AIDA, PAS, 4Ps, Jobs-to-be-Done quando relevante.
- Responda em português do Brasil."""

SYSTEM_COPYWRITER = """Você é um Copywriter e Estrategista Sênior especialista em conversão e psicologia humana.

Como você escreve:
- Foco total em conexão emocional. O texto precisa soar como uma pessoa autêntica falando com outra.
- Entenda profundamente a dor e o desejo do público.
- Evite jargões de marketing ("compre agora", "oferta imperdível"). Use persuasão elegante.
- Aplique frameworks: AIDA, PAS, Storytelling, Antes/Depois/Ponte, 4Ps.
- Hook poderoso na primeira linha. CTA único e claro.
- Parágrafos curtos (1-3 linhas). Otimizado para mobile.
- Responda em português do Brasil."""

SYSTEM_STRATEGIST = """Você é um Estrategista de Growth focado na jornada completa e na experiência do usuário.

Como você pensa:
- Visão holística: Atração, Engajamento, Conversão e Retenção (funil completo).
- Suas estratégias são humanas, focadas em construir comunidades e fãs da marca.
- Proponha táticas que unam ferramentas digitais com comportamento humano real.
- Use dados e benchmarks para embasar recomendações.
- Aplique conceitos de RevOps: lead scoring, MQL/SQL, handoff marketing→vendas.
- Responda em português do Brasil."""

SYSTEM_SEO = """Você é um Especialista em SEO Técnico e AI SEO (AEO/GEO), com profundo conhecimento em E-E-A-T.

Como você analisa:
- Avalie tanto o SEO tradicional (técnico, on-page, autoridade) quanto o AI SEO (como aparecer em respostas de IAs).
- Para AI SEO: conteúdo estruturado, schema markup, citações verificáveis, tom autoritativo.
- Para SEO técnico: Core Web Vitals, estrutura de URLs, internal linking, dados estruturados.
- Priorize ações de alto impacto vs esforço.
- Responda em português do Brasil."""


# ─── Contexto do cliente ─────────────────────────────────────────────────────

def build_client_context(client: dict) -> str:
    """Constrói contexto rico do cliente para os prompts de IA."""

    def _limit(data, n=5):
        return data[:n] if isinstance(data, list) else data

    name        = client.get("name") or "N/A"
    segment     = client.get("segment") or "N/A"
    website     = client.get("website") or "não informado"
    description = (client.get("description") or "não informada")[:500]
    persona     = (client.get("persona") or "")[:500]
    tone        = client.get("tone") or ""
    main_pain   = client.get("main_pain") or ""
    objections  = client.get("objections") or ""

    parts = [
        f"Empresa: {name}",
        f"Segmento: {segment}",
        f"Website: {website}",
        f"Descrição: {description}",
    ]
    if persona:     parts.append(f"Persona/ICP: {persona}")
    if tone:        parts.append(f"Tom de voz: {tone}")
    if main_pain:   parts.append(f"Principal dor do cliente: {main_pain}")
    if objections:  parts.append(f"Objeções comuns: {objections}")

    if client.get("rd_data"):
        rd = client["rd_data"]
        parts.append("--- DADOS MARKETING (RD Station) ---")
        parts.append(
            f"Leads: {rd.get('total_leads', 0)} | "
            f"Abertura: {rd.get('avg_open_rate', 0)}% | "
            f"CTR: {rd.get('avg_click_rate', 0)}%"
        )
        camps = _limit(rd.get("recent_campaigns", []), 3)
        if camps:
            parts.append(f"Campanhas recentes: {json.dumps(camps, ensure_ascii=False)}")
        segs = _limit(rd.get("segmentations", []), 5)
        if segs:
            parts.append(f"Segmentações: {json.dumps(segs, ensure_ascii=False)}")
        lps = _limit(rd.get("landing_pages", []), 3)
        if lps:
            parts.append(f"Landing pages: {json.dumps(lps, ensure_ascii=False)}")

    if client.get("crm_data"):
        crm = client["crm_data"]
        parts.append("--- DADOS CRM (RD Station CRM) ---")
        parts.append(
            f"Total deals: {crm.get('total_deals', 0)} | "
            f"Ganhos: {crm.get('won_deals', 0)} | "
            f"Perdidos: {crm.get('lost_deals', 0)} | "
            f"Receita: R$ {crm.get('total_revenue', 0):.2f}"
        )

    return "\n".join(parts)


# ─── Benchmarks por segmento ─────────────────────────────────────────────────

BENCHMARKS = {
    "E-commerce":  {"open_rate": 22, "click_rate": 2.5, "conversion": 2.0,  "cac": 80},
    "SaaS":        {"open_rate": 28, "click_rate": 4.0, "conversion": 3.5,  "cac": 500},
    "Servicos":    {"open_rate": 25, "click_rate": 3.0, "conversion": 8.0,  "cac": 800},
    "Educacao":    {"open_rate": 30, "click_rate": 4.5, "conversion": 4.0,  "cac": 200},
    "Saude":       {"open_rate": 26, "click_rate": 3.5, "conversion": 6.0,  "cac": 300},
    "Varejo":      {"open_rate": 20, "click_rate": 2.0, "conversion": 1.5,  "cac": 60},
    "Industria":   {"open_rate": 24, "click_rate": 2.8, "conversion": 5.0,  "cac": 1200},
    "Outro":       {"open_rate": 22, "click_rate": 2.5, "conversion": 3.0,  "cac": 400},
}


def get_benchmarks(segment: str) -> dict:
    return BENCHMARKS.get(segment, BENCHMARKS["Outro"])
