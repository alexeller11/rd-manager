import asyncio
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval

router = APIRouter()

# fix #1: lock para garantir que os ALTER TABLE não rodem em paralelo
_clients_table_initialized = False
_clients_table_lock = asyncio.Lock()


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
# INIT TABLES (RETROCOMPATÍVEL)
# =============================

async def _ensure_clients_table():
    global _clients_table_initialized
    if _clients_table_initialized:
        return
    async with _clients_table_lock:
        if _clients_table_initialized:
            return

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # SQLite does not support ADD COLUMN IF NOT EXISTS, so we need to check if the columns exist first
        columns = await db_fetch_all("PRAGMA table_info(clients)")
        column_names = [column["name"] for column in columns]
        if "created_at" not in column_names:
            await db_execute(
                "ALTER TABLE clients ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP;"
            )
        if "updated_at" not in column_names:
            await db_execute(
                "ALTER TABLE clients ADD COLUMN updated_at DATETIME DEFAULT CURRENT_TIMESTAMP;"
            )

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS rd_credentials (
                client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
                access_token TEXT,
                refresh_token TEXT,
                expires_at DATETIME,
                updated_at DATETIME
            )
            """
        )

        _clients_table_initialized = True


# =============================
# FUNÇÃO CRÍTICA DE COMPATIBILIDADE
# =============================

# fix #3: retorna None em vez de lançar HTTPException —
# os callers em intelligence.py, agency_dashboard.py e rd_station.py
# verificam `if not client` e precisam receber None para funcionar corretamente.
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

    return await db_fetch_one(query, client_id)  # None se não encontrado


# =============================
# LISTAR CLIENTES
# =============================

# fix #2: serializa created_at/updated_at para str — asyncpg.Record não converte datetime
def _serialize_client(row) -> dict:
    d = dict(row)
    for field in ("created_at", "updated_at"):
        if field in d and d[field] is not None:
            d[field] = str(d[field])
    return d


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
        COALESCE(rc.updated_at, c.updated_at, c.created_at) AS updated_at,
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
    return [_serialize_client(r) for r in rows] if rows else []


# =============================
# DETALHE CLIENTE
# =============================

@router.get("/{client_id}")
async def get_client(client_id: int):
    client = await fetch_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Cliente não encontrado")
    return _serialize_client(client)


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
        "SELECT id, name, segment, website, description FROM clients WHERE id = $1",
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
