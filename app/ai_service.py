import json
from typing import Any

import httpx
import google.generativeai as genai

from app.core.settings import get_settings

settings = get_settings()

if settings.gemini_api_key:
    try:
        genai.configure(api_key=settings.gemini_api_key)
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")


SYSTEM_EXPERT = (
    "Você é um Consultor de Marketing Estratégico Sênior para agências. "
    "Responda em português do Brasil com profundidade, clareza, senso crítico e foco em ação."
)

SYSTEM_STRATEGIST = (
    "Você é um Estrategista de Growth e CRM para agências. "
    "Responda em português do Brasil com visão prática, priorização e foco em execução."
)

SYSTEM_SEO = (
    "Você é um Especialista em SEO Técnico, CRO e performance de páginas. "
    "Responda em português do Brasil com foco em oportunidades reais de ganho."
)

SYSTEM_COPYWRITER = (
    "Você é um Copywriter de alta conversão para agências. "
    "Escreva em português do Brasil com persuasão, clareza e naturalidade."
)

SYSTEM_DEFAULT = SYSTEM_STRATEGIST


def _strip_markdown_json(raw: str) -> str:
    return raw.strip().replace("```json", "").replace("```", "").strip()


async def _call_groq(prompt: str, system: str | None = None, max_tokens: int = 2000, temperature: float = 0.4) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("Groq não configurado")

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": system or SYSTEM_DEFAULT},
            {"role": "user", "content": prompt[:20000]},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.groq_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if res.status_code != 200:
        raise RuntimeError(f"Groq falhou: {res.status_code} | {res.text[:300]}")

    return res.json()["choices"][0]["message"]["content"]


async def _call_openai(prompt: str, system: str | None = None, max_tokens: int = 2000, temperature: float = 0.4) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI não configurada")

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": system or SYSTEM_DEFAULT},
            {"role": "user", "content": prompt[:20000]},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    async with httpx.AsyncClient(timeout=60.0) as client:
        res = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {settings.openai_api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    if res.status_code != 200:
        raise RuntimeError(f"OpenAI falhou: {res.status_code} | {res.text[:300]}")

    return res.json()["choices"][0]["message"]["content"]


async def _call_gemini(prompt: str, system: str | None = None, max_tokens: int = 2000, temperature: float = 0.4) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini não configurado")

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=system or SYSTEM_DEFAULT,
    )

    response = model.generate_content(
        prompt[:30000],
        generation_config=genai.types.GenerationConfig(
            max_output_tokens=max_tokens,
            temperature=temperature,
        ),
    )

    if not response or not response.text:
        raise RuntimeError("Gemini sem resposta")

    return response.text


async def call_ai(
    prompt: str,
    system: str | None = None,
    max_tokens: int = 2000,
    temperature: float = 0.4,
) -> str:
    errors = []

    for provider in ("groq", "openai", "gemini"):
        try:
            if provider == "groq":
                return await _call_groq(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
            if provider == "openai":
                return await _call_openai(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
            if provider == "gemini":
                return await _call_gemini(prompt, system=system, max_tokens=max_tokens, temperature=temperature)
        except Exception as e:
            errors.append(f"{provider}: {e}")

    return "IA indisponível no momento.\n" + "\n".join(errors)


async def generate_text(prompt: str) -> str:
    return await call_ai(prompt=prompt, system=SYSTEM_DEFAULT, max_tokens=2000, temperature=0.4)


async def call_ai_json(
    prompt: str,
    system: str | None = None,
    schema_description: str | None = None,
    max_tokens: int = 2000,
) -> dict[str, Any]:
    json_instruction = """
Responda EXCLUSIVAMENTE em JSON válido.
Não use markdown.
Não explique antes.
Não explique depois.
"""
    if schema_description:
        json_instruction += f"\nEstrutura esperada:\n{schema_description}\n"

    raw = await call_ai(
        prompt=prompt,
        system=f"{system or SYSTEM_STRATEGIST}\n\n{json_instruction}",
        max_tokens=max_tokens,
        temperature=0.2,
    )

    cleaned = _strip_markdown_json(raw)
    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
        return {"data": parsed}
    except Exception:
        return {
            "error": "json_parse_failed",
            "raw": raw,
        }


def build_client_context(client: dict) -> str:
    name = client.get("name") or "Empresa"
    segment = client.get("segment") or "Não informado"
    description = client.get("description") or "Sem descrição"
    website = client.get("website") or "Não informado"
    persona = client.get("persona") or "Não informado"
    tone = client.get("tone") or "Não informado"
    main_pain = client.get("main_pain") or "Não informado"
    objections = client.get("objections") or "Não informado"

    parts = [
        f"Empresa: {name}",
        f"Segmento: {segment}",
        f"Website: {website}",
        f"Descrição: {description}",
        f"Persona: {persona}",
        f"Tom de voz: {tone}",
        f"Principal dor: {main_pain}",
        f"Objeções comuns: {objections}",
    ]

    rd_data = client.get("rd_data") or {}
    if rd_data:
        parts.append(
            "Resumo RD: "
            f"Leads={rd_data.get('total_leads', 0)} | "
            f"Emails recentes={len(rd_data.get('recent_campaigns', []))} | "
            f"Landing pages={len(rd_data.get('landing_pages', []))} | "
            f"Automações={len(rd_data.get('automations', []))}"
        )

    crm_data = client.get("crm_data") or {}
    if crm_data:
        parts.append(
            f"Resumo CRM: Negócios={crm_data.get('total_deals', 0)} | "
            f"Ganhos={crm_data.get('won_deals', 0)}"
        )

    return "\n".join(parts)


def get_benchmarks(segment: str = "Outro") -> dict:
    benchmarks = {
        "E-commerce": {"open_rate": 15.0, "click_rate": 2.1, "conversion": 1.5},
        "SaaS": {"open_rate": 21.0, "click_rate": 2.4, "conversion": 3.0},
        "Servicos": {"open_rate": 19.0, "click_rate": 2.5, "conversion": 5.0},
        "Educacao": {"open_rate": 24.0, "click_rate": 2.8, "conversion": 4.0},
        "Saude": {"open_rate": 22.0, "click_rate": 2.3, "conversion": 6.0},
        "Varejo": {"open_rate": 14.0, "click_rate": 1.9, "conversion": 1.2},
        "Industria": {"open_rate": 18.0, "click_rate": 2.2, "conversion": 2.5},
        "Outro": {"open_rate": 18.0, "click_rate": 2.0, "conversion": 2.0},
    }
    return benchmarks.get(segment, benchmarks["Outro"])
