from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval

router = APIRouter()


# =============================
# SCHEMAS
# =============================

class ClientCreate(BaseModel):
    name: str
    segment: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    segment: Optional[str] = None
    website: Optional[str] = None
    description: Optional[str] = None


# =============================
# INIT TABLES
# =============================

async def _ensure_clients_table():
    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS clients (
            id SERIAL PRIMARY KEY,
            name TEXT NOT NULL,
            segment TEXT,
            website TEXT,
            description TEXT,
            rd_token TEXT,
            rd_refresh_token TEXT,
            rd_crm_token TEXT,
            rd_account_id TEXT,
            persona TEXT,
            tone TEXT,
            main_pain TEXT,
            objections TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_credentials (
            client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        """
    )


# =============================
# FUNÇÃO CRÍTICA DE COMPATIBILIDADE
# =============================

async def fetch_client(client_id: int):
    await _ensure_clients_table()

    query = """
    SELECT
        c.*,
        CASE
            WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
            WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
            ELSE FALSE
        END AS rd_connected,
        CASE
            WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
            WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
            ELSE FALSE
        END AS rd_token_set
    FROM clients c
    LEFT JOIN rd_credentials rc
        ON rc.client_id = c.id
    WHERE c.id = $1
    """

    client = await db_fetch_one(query, client_id)

    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    return client


# =============================
# LISTAR CLIENTES
# =============================

@router.get("/")
async def list_clients():
    await _ensure_clients_table()

    query = """
    SELECT
        c.id,
        c.name,
        c.segment,
        c.website,
        c.description,
        c.created_at,
        c.updated_at,
        CASE
            WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
            WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
            ELSE FALSE
        END AS rd_connected,
        CASE
            WHEN rc.access_token IS NOT NULL AND TRIM(rc.access_token) <> '' THEN TRUE
            WHEN c.rd_token IS NOT NULL AND TRIM(c.rd_token) <> '' THEN TRUE
            ELSE FALSE
        END AS rd_token_set
    FROM clients c
    LEFT JOIN rd_credentials rc
        ON rc.client_id = c.id
    ORDER BY c.id DESC
    """

    rows = await db_fetch_all(query)
    return rows or []


# =============================
# DETALHE CLIENTE
# =============================

@router.get("/{client_id}")
async def get_client(client_id: int):
    return await fetch_client(client_id)


# =============================
# CRIAR CLIENTE
# =============================

@router.post("/")
async def create_client(payload: ClientCreate):
    await _ensure_clients_table()

    now = datetime.now(timezone.utc)

    client_id = await db_fetchval(
        """
        INSERT INTO clients (
            name,
            segment,
            website,
            description,
            created_at,
            updated_at
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        RETURNING id
        """,
        payload.name,
        payload.segment,
        payload.website,
        payload.description,
        now,
        now,
    )

    if not client_id:
        raise HTTPException(status_code=500, detail="Erro ao criar cliente")

    return {
        "ok": True,
        "client_id": client_id,
        "message": "Cliente criado com sucesso",
    }


# =============================
# ATUALIZAR CLIENTE
# =============================

@router.put("/{client_id}")
async def update_client(client_id: int, payload: ClientUpdate):
    await _ensure_clients_table()

    current = await db_fetch_one(
        """
        SELECT id, name, segment, website, description
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )

    if not current:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    await db_execute(
        """
        UPDATE clients
        SET
            name = $2,
            segment = $3,
            website = $4,
            description = $5,
            updated_at = $6
        WHERE id = $1
        """,
        client_id,
        payload.name if payload.name is not None else current["name"],
        payload.segment if payload.segment is not None else current.get("segment"),
        payload.website if payload.website is not None else current.get("website"),
        payload.description if payload.description is not None else current.get("description"),
        datetime.now(timezone.utc),
    )

    return {"ok": True, "message": "Cliente atualizado com sucesso"}


# =============================
# EXCLUIR CLIENTE
# =============================

@router.delete("/{client_id}")
async def delete_client(client_id: int):
    await _ensure_clients_table()

    existing = await db_fetch_one("SELECT id FROM clients WHERE id = $1", client_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")

    await db_execute("DELETE FROM clients WHERE id = $1", client_id)

    return {"ok": True, "message": "Cliente excluído com sucesso"}
