import httpx
from fastapi import APIRouter
from bs4 import BeautifulSoup

router = APIRouter()


@router.post("/analyze")
async def analyze_page(data: dict):
    url = data.get("url")

    async with httpx.AsyncClient() as client:
        response = await client.get(url)

    html = response.text
    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string if soup.title else "Sem title"
    h1 = soup.find("h1")

    issues = []
    if not h1:
        issues.append("Página sem H1")
    if len(title) < 20:
        issues.append("Title fraco")

    return {
        "title": title,
        "h1": h1.text if h1 else None,
        "issues": issues,
        "seo_score": 70,
        "copy_score": 65
    }
