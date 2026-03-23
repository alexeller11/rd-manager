"""
Serviço de IA — Google Gemini Pro (Principal), Groq e OpenAI como Fallback.
"""
import os
import httpx
import json
import google.generativeai as genai
from typing import Optional

# Configurações das APIs
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-pro")
GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o")

# URLs para Fallback
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Configura o SDK do Gemini se a chave estiver presente
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

async def call_ai(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """
    Chama a API do Gemini Pro como principal. 
    Se falhar, tenta Groq e OpenAI como fallback.
    """
    
    # 1. Tentar Gemini Pro primeiro (se configurado)
    if GEMINI_API_KEY:
        try:
            model = genai.GenerativeModel(
                model_name=GEMINI_MODEL,
                system_instruction=system
            )
            # Gemini usa um formato diferente de max_tokens
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.7
            )
            response = await model.generate_content_async(
                prompt[:30000], 
                generation_config=generation_config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Erro Gemini: {e}")
            # Se falhar, continua para os fallbacks

    # 2. Lista de Fallbacks (Groq e OpenAI)
    fallbacks = []
    if GROQ_API_KEY:
        fallbacks.append({"name": "Groq", "key": GROQ_API_KEY, "url": GROQ_URL, "model": GROQ_MODEL})
    if OPENAI_API_KEY:
        fallbacks.append({"name": "OpenAI", "key": OPENAI_API_KEY, "url": OPENAI_URL, "model": OPENAI_MODEL})

    if not GEMINI_API_KEY and not fallbacks:
        return "⚠️ Erro: Nenhuma chave de IA (GEMINI_API_KEY, GROQ_API_KEY ou OPENAI_API_KEY) configurada."

    # 3. Executar Fallbacks
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    last_error = "Gemini falhou ou não configurado"
    for api in fallbacks:
        try:
            payload = {
                "model": api["model"],
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    api["url"],
                    headers={"Authorization": f"Bearer {api['key']}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                last_error = f"{api['name']} ({resp.status_code})"
        except Exception as e:
            last_error = f"Erro {api['name']}: {str(e)[:50]}"
    
    return f"❌ Falha total na IA. Verifique GEMINI_API_KEY no Railway. (Erro: {last_error})"


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
    
    if client.get("crm_data"):
        crm = client["crm_data"]
        parts.append(f"\nDados RD CRM: Negócios: {crm.get('total_deals', 0)} | Ganhos: {crm.get('won_deals', 0)} | Receita: R$ {crm.get('total_revenue', 0):.2f}")
        
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
