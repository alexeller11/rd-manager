"""RD Station Marketing API v2 — Implementação Resiliente."""
import json
import asyncio
import httpx
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from app.database import db_fetchone, db_fetchval, db_execute, parse_json_field
from app.auth_core import get_valid_mkt_token
from app.ai_service import call_ai, build_client_context, SYSTEM_EXPERT, SYSTEM_STRATEGIST
from app.routers.clients import fetch_client

router = APIRouter()
RD_API = "https://api.rd.services"


# ─── Helpers ─────────────────────────────────────────────────────────────────

def safe_int(val, default=0) -> int:
    try:
        return int(val) if val is not None else default
    except Exception:
        return default


def safe_list(val, *keys) -> list:
    if isinstance(val, list):
        return val
    if isinstance(val, dict):
        for k in keys:
            if k in val and isinstance(val[k], list):
                return val[k]
        for v in val.values():
            if isinstance(v, list):
                return v
    return []


async def rd_get(token: str, path: str, params: dict = None, retries: int = 3) -> tuple:
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    for attempt in range(retries):
        try:
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                r = await client.get(f"{RD_API}{path}", headers=headers, params=params or {})
                if r.status_code == 200:
                    return r.json(), 200, None
                if r.status_code in (500, 502, 503, 504, 429):
                    await asyncio.sleep((2 ** attempt) * 2)
                    continue
                if r.status_code == 404 and "/segmentations/" in path:
                    return {"contacts": [], "total": 0}, 200, None
                return None, r.status_code, f"HTTP {r.status_code}: {r.text[:100]}"
        except Exception as e:
            if attempt < retries - 1:
                await asyncio.sleep(2)
            else:
                return None, 0, str(e)
    return None, 500, "API RD instável após retries"


async def save_rd_snapshot(client_id: int, snap: dict):
    snap_json = json.dumps(snap, ensure_ascii=False)
    try:
        await db_fetchval(
            "INSERT INTO rd_snapshots (client_id, data, snapshot_type) VALUES ($1,$2,$3) RETURNING id",
            client_id, snap_json, "full_sync"
        )
    except Exception as e:
        print(f"Erro ao salvar snapshot RD: {e}")


async def get_rd_snapshot(client_id: int) -> dict:
    row = await db_fetchone(
        "SELECT data, created_at FROM rd_snapshots WHERE client_id=$1 ORDER BY created_at DESC LIMIT 1",
        client_id
    )
    if not row:
        return {}
    return parse_json_field(row["data"])


# ─── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/sync/{client_id}")
async def sync_client(client_id: int):
    token = await get_valid_mkt_token(client_id)
    if not token:
        raise HTTPException(400, "Token RD Marketing não configurado.")

    snap = {
        "total_leads": 0,
        "segmentations": [],
        "landing_pages": [],
        "recent_campaigns": [],
        "automations": [],
    }
    errors = {}

    # Segmentações
    data, st, err = await rd_get(token, "/platform/segmentations", {"page": 1, "page_size": 100})
    if st == 200 and data:
        segs_raw = safe_list(data, "segmentations")
        snap["segmentations"] = [
            {"id": str(s.get("id")), "name": s.get("name"),
             "contacts": safe_int(s.get("contacts_count", s.get("contacts")))}
            for s in segs_raw if s.get("name")
        ]
        base_seg = next((s for s in segs_raw if "base" in (s.get("name") or "").lower()), None)
        snap["total_leads"] = (
            safe_int(base_seg.get("contacts_count")) if base_seg
            else max((safe_int(s.get("contacts_count")) for s in segs_raw), default=0)
        )
    else:
        errors["segmentations"] = err

    # Emails
    data, st, err = await rd_get(token, "/platform/emails", {"page": 1, "page_size": 20})
    if st == 200 and data:
        emails_raw = safe_list(data, "items", "emails")
        campaigns = []
        t_sends = t_opens = t_clicks = 0
        for em in emails_raw:
            sends = max(safe_int(em.get("sends") or em.get("sent_count")), 1)
            opens  = safe_int(em.get("opens") or em.get("open_count"))
            clicks = safe_int(em.get("clicks") or em.get("click_count"))
            t_sends += sends; t_opens += opens; t_clicks += clicks
            campaigns.append({
                "id": em.get("id"),
                "name": em.get("name") or "E-mail",
                "sent": sends, "opens": opens, "clicks": clicks,
                "open_rate":  round(opens  / sends * 100, 1),
                "click_rate": round(clicks / sends * 100, 1),
                "sent_at": em.get("sent_at") or em.get("created_at"),
            })
        snap["recent_campaigns"] = campaigns
        if t_sends > 0:
            snap["avg_open_rate"]  = round(t_opens  / t_sends * 100, 1)
            snap["avg_click_rate"] = round(t_clicks / t_sends * 100, 1)
    else:
        errors["emails"] = err

    # Automações
    data, st, err = await rd_get(token, "/platform/workflows", {"page": 1, "page_size": 50})
    if st == 200 and data:
        workflows = safe_list(data, "workflows", "items")
        snap["automations"] = [
            {"id": w.get("id"), "name": w.get("name"), "status": w.get("status")}
            for w in workflows
        ]
    else:
        errors["automations"] = err

    # Landing pages
    data, st, err = await rd_get(token, "/platform/landing_pages", {"page": 1, "page_size": 20})
    if st == 200 and data:
        lps_raw = safe_list(data, "landing_pages", "items")
        snap["landing_pages"] = [
            {
                "id": lp.get("id"),
                "name": lp.get("name") or lp.get("title"),
                "visitors":    safe_int(lp.get("visitors_count") or lp.get("visits")),
                "conversions": safe_int(lp.get("conversions_count") or lp.get("leads")),
                "conversion_rate": round(
                    safe_int(lp.get("conversions_count") or lp.get("leads")) /
                    max(safe_int(lp.get("visitors_count") or lp.get("visits")), 1) * 100, 1
                ),
            }
            for lp in lps_raw
        ]
    else:
        errors["landing_pages"] = err

    snap["synced_at"] = datetime.now().isoformat()
    snap["sync_errors"] = errors
    await save_rd_snapshot(client_id, snap)

    return {
        "success": True,
        "total_leads": snap.get("total_leads", 0),
        "synced": [k for k in snap if snap[k] and k not in ("sync_errors",)],
        "errors": errors,
    }


@router.get("/diagnose/{client_id}")
async def diagnose_token(client_id: int):
    token = await get_valid_mkt_token(client_id)
    if not token:
        return [{"name": "Token", "status": 0, "ok": False, "error": "Token não configurado"}]
    endpoints = [
        ("Contatos",       "/platform/contacts"),
        ("Segmentações",   "/platform/segmentations"),
        ("Landing Pages",  "/platform/landing_pages"),
        ("E-mails",        "/platform/emails"),
        ("Automações",     "/platform/workflows"),
    ]
    results = []
    for label, path in endpoints:
        data, st, err = await rd_get(token, path, {"page_size": 1})
        results.append({"name": label, "status": st, "ok": st == 200, "error": err})
    return results


@router.get("/leads-analysis/{client_id}")
async def get_leads_analysis(client_id: int, page: int = 1, page_size: int = 50,
                              seg_id: str = ""):
    token = await get_valid_mkt_token(client_id)
    if not token:
        raise HTTPException(400, "Token RD não configurado")
        
    seg_id = str(seg_id).strip() if seg_id and seg_id not in ("null", "undefined") else ""
    path = f"/platform/segmentations/{seg_id}/contacts" if seg_id else "/platform/contacts"
    data, st, err = await rd_get(token, path, {"page": page, "page_size": page_size})
    
    if st != 200 and seg_id:
        data, st, err = await rd_get(token, "/platform/contacts", {"page": page, "page_size": page_size})
            
    if st != 200:
        raise HTTPException(st or 500, f"Erro API RD: {err}")
        
    contacts_raw = safe_list(data, "contacts", "items")
    leads = []
    for c in contacts_raw:
        convs = safe_int(c.get("conversions") or c.get("conversion_count", 0))
        score = min(convs * 15, 100) 
        pot = "alto" if score >= 70 else "medio" if score >= 30 else "baixo"
        leads.append({
            "uuid": c.get("uuid"),
            "name": c.get("name") or c.get("email", "Lead").split("@")[0],
            "email": c.get("email"),
            "score": score,
            "potential": pot,
            "conversions": convs,
            "last_activity": c.get("last_conversion_date") or c.get("updated_at"),
        })
    return {"leads": leads, "total": safe_int(data.get("total", len(leads)))}


class AnalysisRequest(BaseModel):
    client_id: int
    type: Optional[str] = "general"


@router.post("/analyze")
async def analyze_marketing(req: AnalysisRequest):
    client_obj = await fetch_client(req.client_id)
    snap = await get_rd_snapshot(req.client_id)
    context = build_client_context({**client_obj, "rd_data": snap})
    prompt = f"Analise o desempenho de marketing desta empresa.\n\n{context}"
    result = await call_ai(prompt, system=SYSTEM_EXPERT)
    return {"result": result}


@router.post("/flows/generate")
async def generate_flow(req: dict):
    client_id = req.get("client_id")
    objective = req.get("objective")
    flow_type = req.get("flow_type")
    
    client_obj = await fetch_client(client_id)
    context = build_client_context(client_obj)
    
    prompt = f"""Crie um fluxo de automação estratégico com bifurcações inteligentes.
    Objetivo: {objective}
    Tipo: {flow_type}
    Contexto do Cliente: {context}
    
    O fluxo deve incluir:
    1. Gatilho inicial.
    2. Ações de email.
    3. Condições de bifurcação (ex: Abriu email? Clicou no link?).
    4. Caminhos diferentes para 'Sim' e 'Não'.
    
    Responda EXCLUSIVAMENTE em formato JSON estruturado:
    {{
      "name": "Nome do Fluxo",
      "description": "Breve estratégia",
      "nodes": [
        {{"id": 1, "label": "Gatilho", "type": "trigger"}},
        {{"id": 2, "label": "Email 1", "type": "email"}},
        {{"id": 3, "label": "Abriu?", "type": "condition", "paths": {{"yes": 4, "no": 5}}}}
      ]
    }}
    """
    result = await call_ai(prompt, system=SYSTEM_STRATEGIST)
    try:
        # Limpar markdown se houver
        clean_res = result.strip().replace("```json", "").replace("```", "")
        return json.loads(clean_res)
    except:
        return {"error": "IA falhou ao gerar JSON", "raw": result}
