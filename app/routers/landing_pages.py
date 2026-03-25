import httpx
from fastapi import APIRouter
from bs4 import BeautifulSoup
from app.ai_service import generate_text

router = APIRouter()


@router.post("/analyze")
async def analyze_page(data: dict):
    url = data.get("url")

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string if soup.title else ""
    h1 = soup.find("h1")
    text = soup.get_text()

    prompt = f"""
    Analise essa landing page:

    URL: {url}
    TITLE: {title}
    H1: {h1.text if h1 else "sem h1"}
    TEXTO: {text[:2000]}

    Retorne:

    {{
      "seo_score": 0-100,
      "copy_score": 0-100,
      "conversion_score": 0-100,
      "problems": [],
      "quick_wins": [],
      "strategic_suggestions": []
    }}
    """

    ai = await generate_text(prompt)

    return {
        "basic": {
            "title": title,
            "h1": h1.text if h1 else None
        },
        "analysis": ai
    }


@router.post("/generate-copy")
async def generate_lp_copy(data: dict):
    prompt = f"""
    Crie uma landing page completa.

    Produto: {data.get("product")}
    Público: {data.get("audience")}
    Objetivo: {data.get("goal")}

    Inclua:
    - Headline
    - Subheadline
    - Seções
    - CTA
    - Objeções
    """

    result = await generate_text(prompt)

    return {"copy": result}
