"""
Serviço de IA — Groq (Prioridade Atual) com Fallback para OpenAI e Gemini.
"""
import os
import httpx
import json
import google.generativeai as genai
from typing import Optional

# Configurações das APIs
# No seu Railway, apenas GROQ_API_KEY está configurada (groq_key_set: true)
GROQ_API_KEY = os.environ.get("GROQ_API_KEY")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

GROQ_MODEL = os.environ.get("GROQ_MODEL", "llama-3.3-70b-versatile")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-1.5-flash")

# URLs para Fallback
GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
OPENAI_URL = "https://api.openai.com/v1/chat/completions"

# Configura o SDK do Gemini se a chave estiver presente
if GEMINI_API_KEY:
    try:
        genai.configure(api_key=GEMINI_API_KEY)
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")

async def call_ai(prompt: str, system: str = None, max_tokens: int = 2000) -> str:
    """
    Tenta as IAs na ordem de disponibilidade das chaves.
    Atualmente no seu Railway: Groq > OpenAI > Gemini.
    """
    
    # Mensagens para o formato OpenAI/Groq
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt[:20000]})

    # 1. Tentar Groq (Única chave presente no seu diagnóstico)
    if GROQ_API_KEY:
        try:
            payload = {
                "model": GROQ_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    GROQ_URL,
                    headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                
                # Se der 401 (Unauthorized), a chave Groq está errada ou expirou
                if resp.status_code == 401:
                    print(f"⚠️ Erro 401 na Groq: Chave inválida ou expirada.")
                else:
                    print(f"Erro Groq: {resp.status_code} - {resp.text}")
        except Exception as e:
            print(f"Erro ao chamar Groq: {e}")

    # 2. Tentar OpenAI (Fallback 1)
    if OPENAI_API_KEY:
        try:
            payload = {
                "model": OPENAI_MODEL,
                "messages": messages,
                "max_tokens": max_tokens,
                "temperature": 0.7,
            }
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(
                    OPENAI_URL,
                    headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
                    json=payload,
                )
                if resp.status_code == 200:
                    return resp.json()["choices"][0]["message"]["content"]
                print(f"Erro OpenAI: {resp.status_code}")
        except Exception as e:
            print(f"Erro OpenAI: {e}")

    # 3. Tentar Gemini (Fallback 2)
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
            response = model.generate_content(
                prompt[:30000], 
                generation_config=generation_config
            )
            if response and response.text:
                return response.text
        except Exception as e:
            print(f"Erro Gemini: {e}")
    
    # Se chegamos aqui, nada funcionou
    if not GROQ_API_KEY and not OPENAI_API_KEY and not GEMINI_API_KEY:
        return "❌ Nenhuma chave de IA configurada. Adicione OPENAI_API_KEY ou corrija a GROQ_API_KEY no Railway."
    
    return "❌ Erro na IA. A chave Groq presente no seu Railway pode estar expirada ou inválida (Erro 401). Verifique-a ou adicione uma OPENAI_API_KEY."


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

def get_benchmarks(segment: str = "Outro") -> dict:
    """Retorna benchmarks médios por segmento de mercado."""
    b = {
        "E-commerce": {"open_rate": 15.0, "click_rate": 2.1, "conversion": 1.5},
        "SaaS":       {"open_rate": 21.0, "click_rate": 2.4, "conversion": 3.0},
        "Servicos":   {"open_rate": 19.0, "click_rate": 2.5, "conversion": 5.0},
        "Educacao":   {"open_rate": 24.0, "click_rate": 2.8, "conversion": 4.0},
        "Saude":      {"open_rate": 22.0, "click_rate": 2.3, "conversion": 6.0},
        "Varejo":     {"open_rate": 14.0, "click_rate": 1.9, "conversion": 1.2},
        "Industria":  {"open_rate": 18.0, "click_rate": 2.2, "conversion": 2.5},
        "Outro":      {"open_rate": 18.0, "click_rate": 2.0, "conversion": 2.0},
    }
    return b.get(segment, b["Outro"])
