"""
Serviço de IA — Google Gemini Pro (Principal) com Fallback.
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
            generation_config = genai.types.GenerationConfig(
                max_output_tokens=max_tokens,
                temperature=0.7
            )
            # Nota: O SDK do Google AI Studio é síncrono para chamadas simples, 
            # mas usamos a versão assíncrona se disponível ou rodamos em thread se necessário.
            # Aqui usamos a versão simplificada para garantir funcionamento.
            response = model.generate_content(
                prompt[:30000], 
                generation_config=generation_config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Erro Gemini: {e}")

    # 2. Lista de Fallbacks
    fallbacks = []
    if GROQ_API_KEY:
        fallbacks.append({"name": "Groq", "key": GROQ_API_KEY, "url": GROQ_URL, "model": GROQ_MODEL})
    if OPENAI_API_KEY:
        fallbacks.append({"name": "OpenAI", "key": OPENAI_API_KEY, "url": OPENAI_URL, "model": OPENAI_MODEL})

    if not GEMINI_API_KEY and not fallbacks:
        return "⚠️ Erro: Configure GEMINI_API_KEY no Railway para habilitar a IA."

    # 3. Executar Fallbacks
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    last_error = "Gemini falhou"
    for api_config in fallbacks:
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
                    headers={"Authorization": f"Bearer {api_config['key']}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                last_error = f"{api_config['name']} ({resp.status_code})"
        except Exception as e:
            last_error = f"Erro {api_config['name']}: {str(e)[:50]}"
    
    return f"❌ IA Indisponível. Erro: {last_error}. Verifique GEMINI_API_KEY."


# --- Personas ---
SYSTEM_EXPERT = "Você é um Consultor de Marketing Estratégico Sênior. Responda em Português do Brasil com foco em resultados reais."
SYSTEM_STRATEGIST = "Você é um Estrategista de Growth focado em funil de vendas e CRM. Responda em Português do Brasil."
SYSTEM_SEO = "Você é um Especialista em SEO Técnico e Estratégico (AEO/GEO). Responda em Português do Brasil com foco em visibilidade e autoridade."
SYSTEM_COPYWRITER = "Você é um Copywriter de Resposta Direta focado em conversão e persuasão. Responda em Português do Brasil com foco em vendas."

def build_client_context(client: dict) -> str:
    """Constrói contexto do cliente para a IA."""
    name = client.get("name") or "Empresa"
    segment = client.get("segment") or "Não informado"
    description = client.get("description") or "Sem descrição"
    
    parts = [f"Empresa: {name}", f"Segmento: {segment}", f"Descrição: {description}"]
    
    if client.get("crm_data"):
        crm = client["crm_data"]
        parts.append(f"\nDados CRM: Negócios: {crm.get('total_deals', 0)} | Ganhos: {crm.get('won_deals', 0)}")
        
    return "\n".join(parts)
