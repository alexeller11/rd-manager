from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.ai_service import SYSTEM_STRATEGIST, call_ai_json
from app.auth_core import (
    clear_crm_credentials,
    clear_mkt_credentials,
    get_rd_credentials,
    save_crm_token,
    save_mkt_token,
)
from app.database import db_execute, db_fetchall, db_fetchone, db_fetchval

router = APIRouter()


class ClientBase(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    segment: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None
    rd_account_id: Optional[str] = None
    persona: Optional[str] = None
    tone: Optional[str] = None
    main_pain: Optional[str] = None
    objections: Optional[str] = None


class ClientCreate(ClientBase):
    rd_token: Optional[str] = None
    rd_refresh_token: Optional[str] = None
    rd_crm_token: Optional[str] = None


class ClientUpdate(ClientBase):
    rd_token: Optional[str] = None
    rd_refresh_token: Optional[str] = None
    rd_crm_token: Optional[str] = None


def _sanitize(client: dict, creds: dict) -> dict:
    return {
        "id": client["id"],
        "name": client["name"],
        "segment": client.get("segment"),
        "website": client.get("website"),
        "description": client.get("description"),
        "rd_account_id": client.get("rd_account_id"),
        "persona": client.get("persona"),
        "tone": client.get("tone"),
        "main_pain": client.get("main_pain"),
        "objections": client.get("objections"),
        "created_at": client.get("created_at"),
        "updated_at": client.get("updated_at"),
        "rd_token_set": bool((creds.get("rd_token") or "").strip()),
        "rd_refresh_token_set": bool((creds.get("rd_refresh_token") or "").strip()),
        "crm_token_set": bool((creds.get("rd_crm_token") or "").strip()),
        "token_status": creds.get("token_status", "unknown"),
        "last_validated_at": creds.get("last_validated_at"),
        "last_refresh_at": creds.get("last_refresh_at"),
    }


async def fetch_client(client_id: int) -> dict | None:
    return await db_fetchone("SELECT * FROM clients WHERE id = $1", client_id)


@router.get("/")
async def list_clients():
    rows = await db_fetchall("SELECT * FROM clients ORDER BY created_at DESC")
    result = []
    for row in rows:
        creds = await get_rd_credentials(row["id"])
        result.append(_sanitize(row, creds))
    return result


@router.get("/{client_id}")
async def get_client(client_id: int):
    row = await fetch_client(client_id)
    if not row:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    creds = await get_rd_credentials(client_id)
    return _sanitize(row, creds)


@router.post("/")
async def create_client(data: ClientCreate):
    client_id = await db_fetchval(
        """
        INSERT INTO clients
            (name, segment, website, description, rd_account_id, persona, tone, main_pain, objections)
        VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
        RETURNING id
        """,
        data.name,
        data.segment,
        data.website,
        data.description,
        data.rd_account_id,
        data.persona,
        data.tone,
        data.main_pain,
        data.objections,
    )

    if data.rd_token:
        await save_mkt_token(client_id, data.rd_token.strip(), (data.rd_refresh_token or "").strip())
    if data.rd_crm_token:
        await save_crm_token(client_id, data.rd_crm_token.strip())

    row = await fetch_client(client_id)
    creds = await get_rd_credentials(client_id)
    return _sanitize(row, creds)


@router.put("/{client_id}")
async def update_client(client_id: int, data: ClientUpdate):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    await db_execute(
        """
        UPDATE clients
           SET name = $1,
               segment = $2,
               website = $3,
               description = $4,
               rd_account_id = $5,
               persona = $6,
               tone = $7,
               main_pain = $8,
               objections = $9,
               updated_at = $10
         WHERE id = $11
        """,
        data.name,
        data.segment,
        data.website,
        data.description,
        data.rd_account_id,
        data.persona,
        data.tone,
        data.main_pain,
        data.objections,
        existing.get("updated_at") if existing.get("updated_at") else None,
        client_id,
    )

    if data.rd_token is not None:
        if data.rd_token.strip():
            await save_mkt_token(client_id, data.rd_token.strip(), (data.rd_refresh_token or "").strip())
        else:
            await clear_mkt_credentials(client_id)

    if data.rd_crm_token is not None:
        if data.rd_crm_token.strip():
            await save_crm_token(client_id, data.rd_crm_token.strip())
        else:
            await clear_crm_credentials(client_id)

    row = await fetch_client(client_id)
    creds = await get_rd_credentials(client_id)
    return _sanitize(row, creds)


@router.delete("/{client_id}")
async def delete_client(client_id: int):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    await db_execute("DELETE FROM clients WHERE id = $1", client_id)
    return {"success": True}


@router.get("/{client_id}/credentials/status")
async def get_credentials_status(client_id: int):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    creds = await get_rd_credentials(client_id)
    return {
        "client_id": client_id,
        "rd_token_set": bool((creds.get("rd_token") or "").strip()),
        "rd_refresh_token_set": bool((creds.get("rd_refresh_token") or "").strip()),
        "crm_token_set": bool((creds.get("rd_crm_token") or "").strip()),
        "token_status": creds.get("token_status", "unknown"),
        "last_validated_at": creds.get("last_validated_at"),
        "last_refresh_at": creds.get("last_refresh_at"),
    }


@router.post("/{client_id}/credentials/marketing")
async def set_marketing_credentials(client_id: int, payload: dict):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    token = (payload.get("rd_token") or "").strip()
    refresh = (payload.get("rd_refresh_token") or "").strip()

    if not token:
        raise HTTPException(status_code=400, detail="rd_token não informado")

    await save_mkt_token(client_id, token, refresh)
    return {"success": True}


@router.post("/{client_id}/credentials/crm")
async def set_crm_credentials(client_id: int, payload: dict):
    existing = await fetch_client(client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    token = (payload.get("rd_crm_token") or "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="rd_crm_token não informado")

    await save_crm_token(client_id, token)
    return {"success": True}


@router.post("/suggest-data")
async def suggest_client_data(payload: dict):
    url = (payload.get("website") or "").strip()
    if not url:
        raise HTTPException(status_code=400, detail="URL do site não informada")

    if not url.startswith("http"):
        url = "https://" + url

    schema = """
{
  "segment": "E-commerce | SaaS | Servicos | Educacao | Saude | Varejo | Industria | Outro",
  "description": "descrição curta",
  "persona": "persona",
  "tone": "tom de voz",
  "main_pain": "principal dor",
  "objections": "objeções comuns"
}
"""

    result = await call_ai_json(
        prompt=f"""
Analise o site abaixo e sugira dados para cadastro de marketing.

URL: {url}

Critérios:
1. Responda em Português do Brasil.
2. Seja objetivo.
3. Não invente dados absurdos.
4. Se não tiver certeza, use formulações prudentes.
""",
        system=SYSTEM_STRATEGIST,
        schema_description=schema,
        max_tokens=1200,
    )
    return result
