import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter

from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze")
async def analyze_page(data: dict):
    url = data.get("url")
    if not url:
        return {"error": "URL não informada"}

    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        response = await client.get(url)

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""
    h1 = soup.find("h1")
    h1_text = h1.get_text(strip=True) if h1 else ""
    meta_desc = ""
    meta = soup.find("meta", attrs={"name": "description"})
    if meta and meta.get("content"):
        meta_desc = meta.get("content").strip()

    body_text = soup.get_text(separator=" ", strip=True)[:3000]

    prompt = f"""
Analise esta landing page no nível de uma agência de alta performance.

URL: {url}
TITLE: {title}
META DESCRIPTION: {meta_desc}
H1: {h1_text}
TEXTO: {body_text}

Avalie:
- SEO
- Copy
- Conversão
- Performance percebida
- Clareza da oferta
- CTA
- Estrutura

Entregue:
- nota geral
- nota SEO
- nota copy
- nota conversão
- problemas
- ganhos rápidos
- melhorias estratégicas
"""
    analysis = await generate_text(prompt)

    return {
        "basic": {
            "url": url,
            "title": title,
            "meta_description": meta_desc,
            "h1": h1_text,
        },
        "analysis": analysis,
    }


@router.post("/generate-copy")
async def generate_lp_copy(data: dict):
    prompt = f"""
Crie a copy de uma landing page de alta conversão.

Produto: {data.get("product")}
Público: {data.get("audience")}
Objetivo: {data.get("goal")}

Entregue:
- headline
- subheadline
- seções
- CTA
- prova social
- quebra de objeções
"""
    result = await generate_text(prompt)
    return {"copy": result}
