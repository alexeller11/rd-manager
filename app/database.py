"""
Camada de banco de dados unificada.
- PostgreSQL em produção
- SQLite opcional para dev local
- Fail-fast no boot
- Schema com separação de credenciais
"""
import os
import re
import json
import asyncio
import aiosqlite
import asyncpg
from typing import Any

from app.core.settings import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

_pg_pool: asyncpg.Pool | None = None
_pg_lock = asyncio.Lock()


def _is_sqlite() -> bool:
    return DATABASE_URL.startswith("sqlite")


def _sqlite_path() -> str:
    return DATABASE_URL.replace("sqlite:///", "")


def _to_sqlite_params(query: str) -> str:
    return re.sub(r"\$\d+", "?", query)


async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        async with _pg_lock:
            if _pg_pool is None:
                _pg_pool = await asyncpg.create_pool(
                    DATABASE_URL,
                    min_size=1,
                    max_size=10,
                    command_timeout=30,
                )
    return _pg_pool


async def close_db() -> None:
    global _pg_pool
    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None


async def db_fetchone(query: str, *args) -> dict | None:
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        async with aiosqlite.connect(_sqlite_path()) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sq, args) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def db_fetchall(query: str, *args) -> list[dict]:
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        async with aiosqlite.connect(_sqlite_path()) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sq, args) as cur:
                rows = await cur.fetchall()
                return [dict(r) for r in rows]

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def db_execute(query: str, *args) -> None:
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        async with aiosqlite.connect(_sqlite_path()) as db:
            await db.execute(sq, args)
            await db.commit()
        return

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.execute(query, *args)


async def db_fetchval(query: str, *args):
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        upper_sq = sq.upper()
        sq_exec = sq
        if " RETURNING " in upper_sq:
            idx = upper_sq.index(" RETURNING ")
            sq_exec = sq[:idx]
        async with aiosqlite.connect(_sqlite_path()) as db:
            cur = await db.execute(sq_exec, args)
            await db.commit()
            return cur.lastrowid

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def db_executemany(query: str, args_list: list[tuple | list]) -> None:
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        async with aiosqlite.connect(_sqlite_path()) as db:
            await db.executemany(sq, args_list)
            await db.commit()
        return

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        await conn.executemany(query, args_list)


def parse_json_field(val: Any) -> dict | list:
    if val is None:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}


SCHEMA_SQLITE = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin INTEGER DEFAULT 0,
    created_at TEXT DEFAULT (datetime('now'))
);

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
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rd_credentials (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    encrypted_mkt_token TEXT,
    encrypted_mkt_refresh_token TEXT,
    encrypted_crm_token TEXT,
    token_status TEXT DEFAULT 'unknown',
    last_validated_at TEXT,
    last_refresh_at TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    updated_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    type TEXT,
    prompt TEXT,
    result TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS error_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER,
    endpoint TEXT,
    method TEXT,
    error_message TEXT,
    stack_trace TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS rd_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    data TEXT,
    snapshot_type TEXT DEFAULT 'full_sync',
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS crm_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    data TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS email_strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    type TEXT,
    subject TEXT,
    body TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    name TEXT,
    description TEXT,
    flow_data TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS weekly_analyses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    result TEXT,
    week_ref TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    client_id INTEGER REFERENCES clients(id),
    sync_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    started_at TEXT DEFAULT (datetime('now')),
    finished_at TEXT
);
"""

SCHEMA_PG = """
CREATE TABLE IF NOT EXISTS users (
    id SERIAL PRIMARY KEY,
    username TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

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
);

CREATE TABLE IF NOT EXISTS rd_credentials (
    id SERIAL PRIMARY KEY,
    client_id INTEGER UNIQUE NOT NULL REFERENCES clients(id) ON DELETE CASCADE,
    encrypted_mkt_token TEXT,
    encrypted_mkt_refresh_token TEXT,
    encrypted_crm_token TEXT,
    token_status TEXT DEFAULT 'unknown',
    last_validated_at TIMESTAMPTZ,
    last_refresh_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS analyses (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT,
    prompt TEXT,
    result TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS error_logs (
    id SERIAL PRIMARY KEY,
    client_id INTEGER,
    endpoint TEXT,
    method TEXT,
    error_message TEXT,
    stack_trace TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS rd_snapshots (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    data TEXT,
    snapshot_type TEXT DEFAULT 'full_sync',
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS crm_snapshots (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    data TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS email_strategies (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    type TEXT,
    subject TEXT,
    body TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS flows (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    name TEXT,
    description TEXT,
    flow_data TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS weekly_analyses (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    result TEXT,
    week_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS sync_runs (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    sync_type TEXT NOT NULL,
    status TEXT NOT NULL,
    details TEXT,
    started_at TIMESTAMPTZ DEFAULT NOW(),
    finished_at TIMESTAMPTZ
);
"""


async def _run_pg_schema() -> None:
    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        for stmt in [s.strip() for s in SCHEMA_PG.split(";") if s.strip()]:
            await conn.execute(stmt)


async def _run_sqlite_schema() -> None:
    async with aiosqlite.connect(_sqlite_path()) as db:
        await db.executescript(SCHEMA_SQLITE)
        await db.commit()


async def init_db() -> None:
    try:
        if _is_sqlite():
            await _run_sqlite_schema()
            print("✅ SQLite inicializado com sucesso.")
        else:
            await _run_pg_schema()
            print("✅ PostgreSQL inicializado com sucesso.")
    except Exception as e:
        print(f"❌ Falha crítica ao inicializar banco: {e}")
        raise
