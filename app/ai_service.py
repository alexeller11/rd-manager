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
    """Chama a API do Groq ou OpenAI. Retorna string de erro amigável em caso de falha."""
    
    # 1. Determinar qual API usar
    api_key = None
    url = None
    model = None
    
    if GROQ_API_KEY:
        api_key = GROQ_API_KEY
        url = GROQ_URL
        model = GROQ_MODEL
    elif OPENAI_API_KEY:
        api_key = OPENAI_API_KEY
        url = OPENAI_URL
        model = OPENAI_MODEL
    
    if not api_key:
        return "Erro: Nenhuma chave de API (GROQ_API_KEY ou OPENAI_API_KEY) foi encontrada nas variáveis de ambiente do Railway. Por favor, adicione uma delas para que a IA funcione."

    # 2. Preparar as mensagens
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    payload = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
        "temperature": 0.7,
    }

    # 3. Executar a chamada com tratamento de erro detalhado
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                url,
                headers={
                    "Authorization": f"Bearer {api_key}", 
                    "Content-Type": "application/json"
                },
                json=payload,
            )
            
            if resp.status_code == 401:
                return f"Erro de Autenticação (401): A chave de API fornecida para o modelo {model} é inválida. Verifique se a chave em 'OPENAI_API_KEY' ou 'GROQ_API_KEY' está correta no Railway."
            
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]
            
    except httpx.HTTPStatusError as e:
        error_detail = e.response.text[:200]
        return f"Erro na API de IA ({e.response.status_code}): {error_detail}"
    except Exception as e:
        return f"Erro inesperado na IA: {str(e)}"


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
