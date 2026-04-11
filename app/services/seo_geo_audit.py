import json
import re
from html import unescape
from urllib.parse import urljoin, urlparse

import httpx

from app.database import db_fetch_all, db_fetch_one


TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
META_RE = re.compile(
    r'<meta[^>]+(?:name|property)=["\']([^"\']+)["\'][^>]+content=["\']([^"\']*)["\'][^>]*>',
    re.IGNORECASE | re.DOTALL,
)
H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
H2_RE = re.compile(r"<h2[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
CANONICAL_RE = re.compile(
    r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)["\']',
    re.IGNORECASE | re.DOTALL,
)
ROBOTS_RE = re.compile(
    r'<meta[^>]+name=["\']robots["\'][^>]+content=["\']([^"\']*)["\']',
    re.IGNORECASE | re.DOTALL,
)
SCHEMA_RE = re.compile(
    r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.IGNORECASE | re.DOTALL,
)
LINK_RE = re.compile(r'href=["\']([^"\']+)["\']', re.IGNORECASE | re.DOTALL)
FAQ_TERMS = ("faq", "perguntas frequentes", "pergunta", "duvida", "dúvida")


def _strip_html(text: str) -> str:
    text = re.sub(r"<[^>]+>", " ", text or "")
    text = unescape(text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


async def _fetch_text(url: str) -> tuple[int, str]:
    async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
        res = await client.get(url)
    return res.status_code, res.text


def _extract_meta_map(html: str) -> dict:
    meta = {}
    for key, value in META_RE.findall(html or ""):
        meta[key.lower()] = value
    return meta


def _extract_links(html: str, base_url: str) -> list[str]:
    links = []
    for href in LINK_RE.findall(html or ""):
        if href.startswith("#") or href.startswith("mailto:") or href.startswith("tel:"):
            continue
        links.append(urljoin(base_url, href))
    return list(dict.fromkeys(links))


def _same_host(url_a: str, url_b: str) -> bool:
    return urlparse(url_a).netloc == urlparse(url_b).netloc


async def audit_single_url(url: str) -> dict:
    status_code, html = await _fetch_text(url)

    title_match = TITLE_RE.search(html or "")
    title = _strip_html(title_match.group(1)) if title_match else ""

    meta_map = _extract_meta_map(html or "")
    meta_desc = meta_map.get("description", "")
    robots = meta_map.get("robots")

    h1s = [_strip_html(x) for x in H1_RE.findall(html or "")]
    h2s = [_strip_html(x) for x in H2_RE.findall(html or "")]
    canonical_match = CANONICAL_RE.search(html or "")
    canonical = canonical_match.group(1) if canonical_match else None
    schema_blocks = [x.strip() for x in SCHEMA_RE.findall(html or "") if x.strip()]

    links = _extract_links(html or "", url)
    internal_links = [x for x in links if _same_host(url, x)]
    has_faq = any(term in (html or "").lower() for term in FAQ_TERMS)

    seo_score = 100
    geo_score = 100
    seo_notes = []
    geo_notes = []
    quick_wins = []

    if not title:
        seo_score -= 20
        seo_notes.append("Página sem title.")
        quick_wins.append("Criar title com intenção de busca + marca.")

    if not meta_desc:
        seo_score -= 10
        seo_notes.append("Página sem meta description.")
        quick_wins.append("Escrever meta description objetiva.")

    if len(h1s) == 0:
        seo_score -= 15
        seo_notes.append("Página sem H1.")
        quick_wins.append("Adicionar H1 único alinhado à principal intenção.")

    if not canonical:
        seo_score -= 5
        seo_notes.append("Página sem canonical.")

    if robots and "noindex" in robots.lower():
        seo_score -= 25
        seo_notes.append("Página marcada como noindex.")

    if len(internal_links) < 2:
        seo_score -= 8
        seo_notes.append("Poucos links internos.")

    if not has_faq:
        geo_score -= 12
        geo_notes.append("Sem FAQ ou perguntas frequentes claras.")
        quick_wins.append("Adicionar FAQ com perguntas reais do público.")

    if len(schema_blocks) == 0:
        geo_score -= 10
        geo_notes.append("Sem JSON-LD detectável.")
        quick_wins.append("Adicionar schema em JSON-LD.")

    if len(h2s) < 2:
        geo_score -= 8
        geo_notes.append("Estrutura de subtópicos fraca.")

    return {
        "url": url,
        "status_code": status_code,
        "title": title,
        "meta_description": meta_desc,
        "h1s": h1s,
        "h2s": h2s,
        "canonical": canonical,
        "robots": robots,
        "internal_links_total": len(internal_links),
        "schema_blocks_total": len(schema_blocks),
        "faq_detected": has_faq,
        "seo_score": max(0, seo_score),
        "seo_notes": seo_notes,
        "geo_score": max(0, geo_score),
        "geo_notes": geo_notes,
        "quick_wins": quick_wins,
    }


async def audit_client_website(client_id: int) -> dict:
    client = await db_fetch_one(
        """
        SELECT id, name, website, segment
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    website = str(client.get("website") or "").strip()
    if not website:
        raise Exception("Cliente sem website cadastrado")

    page_audit = await audit_single_url(website)

    return {
        "client": client,
        "website_audit": page_audit,
    }


async def audit_client_landing_pages(client_id: int, limit: int = 20) -> dict:
    client = await db_fetch_one(
        """
        SELECT id, name, website, segment
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )

    if not client:
        raise Exception("Cliente não encontrado")

    rows = await db_fetch_all(
        """
        SELECT object_key, payload, synced_at
        FROM rd_sync_snapshots
        WHERE client_id = $1 AND object_type = 'landing_page'
        ORDER BY synced_at DESC
        LIMIT $2
        """,
        client_id,
        limit,
    ) or []

    audits = []
    for row in rows:
        payload = row.get("payload")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {}

        payload = payload or {}
        url = payload.get("url") or payload.get("public_url") or payload.get("page_url")
        if not url:
            audits.append({
                "object_key": row.get("object_key"),
                "error": "Landing page sem URL pública no payload sincronizado.",
                "payload": payload,
            })
            continue

        audit = await audit_single_url(url)
        audits.append({
            "object_key": row.get("object_key"),
            "url": url,
            "audit": audit,
        })

    return {
        "client": client,
        "landing_pages_total_audited": len(audits),
        "landing_page_audits": audits,
    }
