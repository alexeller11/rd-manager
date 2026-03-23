"""
Serviço de IA — Groq/Llama e OpenAI com suporte robusto e tratamento de erros.
"""
import os
import httpx
import json

# Prioridade: GROQ_API_KEY, se não houver, usa OPENAI_API_KEY
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"


async def call_ai(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """Chama a API do Groq ou OpenAI com fallback automático. Retorna string de erro amigável em caso de falha."""
    
    # 1. Lista de APIs a tentar (Groq primeiro, depois OpenAI)
    apis_to_try = []
    
    if GROQ_API_KEY:
        apis_to_try.append({
            "name": "Groq",
            "api_key": GROQ_API_KEY,
            "url": GROQ_URL,
            "model": GROQ_MODEL
        })
    
    if OPENAI_API_KEY:
        apis_to_try.append({
            "name": "OpenAI",
            "api_key": OPENAI_API_KEY,
            "url": OPENAI_URL,
            "model": OPENAI_MODEL
        })
    
    if not apis_to_try:
        return "⚠️ Erro Crítico: Nenhuma chave de API (GROQ_API_KEY ou OPENAI_API_KEY) foi encontrada no Railway. Configure pelo menos uma delas para que a IA funcione."

    # 2. Preparar as mensagens
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    # 3. Tentar cada API em sequência (fallback automático)
    last_error = None
    for api_config in apis_to_try:
        try:
            payload = {
                "model": api_config["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    api_config["url"],
                    headers={
                        "Authorization": f"Bearer {api_config['api_key']}", 
                        "Content-Type": "application/json"
                    },
                    json=payload,
                )
                
                if resp.status_code == 200:
                    data = resp.json()
                    return data["choices"][0]["message"]["content"]
                elif resp.status_code == 401:
                    last_error = f"Chave {api_config['name']} inválida (401). Tentando próxima..."
                    continue
                elif resp.status_code in (429, 500, 502, 503):
                    last_error = f"API {api_config['name']} indisponível ({resp.status_code}). Tentando próxima..."
                    continue
                else:
                    last_error = f"Erro {api_config['name']} ({resp.status_code}): {resp.text[:100]}"
                    continue
                    
        except Exception as e:
            last_error = f"Erro ao conectar em {api_config['name']}: {str(e)[:100]}"
            continue
    
    # 4. Se todas as APIs falharem, retornar erro informativo
    if last_error:
        return f"❌ Todas as APIs de IA falharam. Último erro: {last_error}. Configure GROQ_API_KEY ou OPENAI_API_KEY válidas no Railway."
    return "❌ Erro inesperado ao chamar IA. Verifique as variáveis de ambiente no Railway."


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
    name = client.get("name") or "Empresa"
    segment = client.get("segment") or "Não informado"
    website = client.get("website") or "Não informado"
    description = client.get("description") or "Sem descrição"
    persona = client.get("persona") or "Público geral"
    
    parts = [
        f"Empresa: {name}",
        f"Segmento: {segment}",
        f"Website: {website}",
        f"Descrição: {description}",
        f"Persona: {persona}"
    ]
    
    if client.get("rd_data"):
        rd = client["rd_data"]
        parts.append(f"\nDados RD Marketing: Leads: {rd.get('total_leads', 0)} | Open Rate: {rd.get('avg_open_rate', 0)}%")
        
    return "\n".join(parts)


def get_benchmarks(segment: str) -> dict:
    """Retorna benchmarks médios por segmento de mercado."""
    benchmarks = {
        "E-commerce": {"open_rate": 15, "click_rate": 2.5, "conversion": 1.5},
        "SaaS":       {"open_rate": 22, "click_rate": 3.0, "conversion": 2.0},
        "Servicos":   {"open_rate": 25, "click_rate": 3.5, "conversion": 3.0},
        "Educacao":   {"open_rate": 20, "click_rate": 2.8, "conversion": 2.5},
        "Saude":      {"open_rate": 28, "click_rate": 4.0, "conversion": 4.0},
        "Varejo":     {"open_rate": 18, "click_rate": 2.2, "conversion": 1.2},
        "Industria":  {"open_rate": 24, "click_rate": 3.2, "conversion": 2.8},
        "Outro":      {"open_rate": 20, "click_rate": 2.5, "conversion": 2.0},
    }
    return benchmarks.get(segment, benchmarks["Outro"])
