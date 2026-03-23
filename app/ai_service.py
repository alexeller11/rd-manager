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

SYSTEM_EXPERT = """Você é um Consultor de Marketing Estratégico de alto nível.
Responda sempre em Português do Brasil. Seja consultivo, estratégico e humano."""

SYSTEM_COPYWRITER = """Você é um Copywriter Sênior especialista em conversão.
Foco em conexão emocional e persuasão elegante. Responda em Português do Brasil."""

SYSTEM_STRATEGIST = """Você é um Estrategista de Growth focado na jornada do usuário.
Pense em funil completo: Atração até Retenção. Responda em Português do Brasil."""


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
