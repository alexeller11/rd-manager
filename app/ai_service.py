import httpx
import google.generativeai as genai

from app.core.settings import get_settings

settings = get_settings()

if settings.gemini_api_key:
    try:
        genai.configure(api_key=settings.gemini_api_key)
    except Exception as e:
        print(f"Erro ao configurar Gemini: {e}")


SYSTEM_DEFAULT = "Você é um estrategista de marketing sênior para agências. Responda em português do Brasil com profundidade, clareza e visão prática."


async def _call_groq(prompt: str) -> str:
    if not settings.groq_api_key:
        raise RuntimeError("Groq não configurado")

    payload = {
        "model": settings.groq_model,
        "messages": [
            {"role": "system", "content": SYSTEM_DEFAULT},
            {"role": "user", "content": prompt[:20000]},
        ],
        "temperature": 0.4,
        "max_tokens": 2000,
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


async def _call_openai(prompt: str) -> str:
    if not settings.openai_api_key:
        raise RuntimeError("OpenAI não configurada")

    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": SYSTEM_DEFAULT},
            {"role": "user", "content": prompt[:20000]},
        ],
        "temperature": 0.4,
        "max_tokens": 2000,
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


async def _call_gemini(prompt: str) -> str:
    if not settings.gemini_api_key:
        raise RuntimeError("Gemini não configurado")

    model = genai.GenerativeModel(
        model_name=settings.gemini_model,
        system_instruction=SYSTEM_DEFAULT,
    )
    response = model.generate_content(prompt[:30000])
    if not response or not response.text:
        raise RuntimeError("Gemini sem resposta")
    return response.text


async def generate_text(prompt: str) -> str:
    errors = []

    for provider in ("groq", "openai", "gemini"):
        try:
            if provider == "groq":
                return await _call_groq(prompt)
            if provider == "openai":
                return await _call_openai(prompt)
            if provider == "gemini":
                return await _call_gemini(prompt)
        except Exception as e:
            errors.append(f"{provider}: {e}")

    return "IA indisponível no momento.\n" + "\n".join(errors)
