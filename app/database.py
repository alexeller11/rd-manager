import os
import re
import json
import asyncio
from typing import Any, Optional

import aiosqlite
import asyncpg

from app.core.settings import get_settings

settings = get_settings()
DATABASE_URL = settings.database_url

_pg_pool: Optional[asyncpg.Pool] = None
_pg_lock = asyncio.Lock()
_sqlite_conn: Optional[aiosqlite.Connection] = None


def _is_postgres() -> bool:
    return DATABASE_URL.startswith("postgresql")


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


async def init_db():
    global _sqlite_conn

    if _is_postgres():
        await get_pg_pool()
        await _init_postgres_schema()
        print("✅ PostgreSQL inicializado com sucesso.")
        return

    if _is_sqlite():
        _sqlite_conn = await aiosqlite.connect(_sqlite_path())
        _sqlite_conn.row_factory = aiosqlite.Row
        await _sqlite_conn.execute("PRAGMA foreign_keys = ON;")
        await _init_sqlite_schema()
        print("✅ SQLite inicializado com sucesso.")
        return

    raise RuntimeError("DATABASE_URL inválida. Use postgresql:// ou sqlite:///")


async def close_db():
    global _pg_pool, _sqlite_conn

    if _pg_pool:
        await _pg_pool.close()
        _pg_pool = None

    if _sqlite_conn:
        await _sqlite_conn.close()
        _sqlite_conn = None


async def db_execute(query: str, *args):
    if _is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            return await conn.execute(query, *args)

    query_sqlite = _to_sqlite_params(query)
    cursor = await _sqlite_conn.execute(query_sqlite, args)
    await _sqlite_conn.commit()
    return cursor


async def db_fetchone(query: str, *args) -> Optional[dict]:
    if _is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    query_sqlite = _to_sqlite_params(query)
    cursor = await _sqlite_conn.execute(query_sqlite, args)
    row = await cursor.fetchone()
    return dict(row) if row else None


async def db_fetchall(query: str, *args) -> list[dict]:
    if _is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]

    query_sqlite = _to_sqlite_params(query)
    cursor = await _sqlite_conn.execute(query_sqlite, args)
    rows = await cursor.fetchall()
    return [dict(r) for r in rows]


async def db_fetchval(query: str, *args):
    if _is_postgres():
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    query_sqlite = _to_sqlite_params(query)

    upper = query_sqlite.upper()
    if " RETURNING " in upper:
        idx = upper.index(" RETURNING ")
        query_sqlite = query_sqlite[:idx]

    cursor = await _sqlite_conn.execute(query_sqlite, args)
    await _sqlite_conn.commit()
    return cursor.lastrowid


# Compatibilidade com arquivos que importam db_fetch_one / db_fetch_all
async def db_fetch_one(query: str, *args) -> Optional[dict]:
    return await db_fetchone(query, *args)


async def db_fetch_all(query: str, *args) -> list[dict]:
    return await db_fetchall(query, *args)


def parse_json_field(value: Any) -> Any:
    if value is None:
        return {}
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return {}
    return {}


async def _init_postgres_schema():
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
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
        """,
        """
        CREATE TABLE IF NOT EXISTS rd_credentials (
            client_id INTEGER PRIMARY KEY REFERENCES clients(id) ON DELETE CASCADE,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            type TEXT,
            prompt TEXT,
            result TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS error_logs (
            id SERIAL PRIMARY KEY,
            client_id INTEGER,
            endpoint TEXT,
            method TEXT,
            error_message TEXT,
            stack_trace TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rd_snapshots (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            data TEXT,
            snapshot_type TEXT DEFAULT 'full_sync',
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS crm_snapshots (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            data TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_strategies (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            type TEXT,
            subject TEXT,
            body TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS flows (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            name TEXT,
            description TEXT,
            flow_data TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS weekly_analyses (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            result TEXT,
            week_ref TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            id SERIAL PRIMARY KEY,
            client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
            sync_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            started_at TIMESTAMPTZ DEFAULT NOW(),
            finished_at TIMESTAMPTZ
        )
        """,
    ]

    pool = await get_pg_pool()
    async with pool.acquire() as conn:
        for stmt in statements:
            await conn.execute(stmt)


async def _init_sqlite_schema():
    statements = [
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
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
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rd_credentials (
            client_id INTEGER PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TEXT,
            updated_at TEXT,
            FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            type TEXT,
            prompt TEXT,
            result TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS error_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            endpoint TEXT,
            method TEXT,
            error_message TEXT,
            stack_trace TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS rd_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            data TEXT,
            snapshot_type TEXT DEFAULT 'full_sync',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS crm_snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS email_strategies (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            type TEXT,
            subject TEXT,
            body TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS flows (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            name TEXT,
            description TEXT,
            flow_data TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS weekly_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            result TEXT,
            week_ref TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS sync_runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            client_id INTEGER,
            sync_type TEXT NOT NULL,
            status TEXT NOT NULL,
            details TEXT,
            started_at TEXT DEFAULT CURRENT_TIMESTAMP,
            finished_at TEXT
        )
        """,
    ]

    for stmt in statements:
        await _sqlite_conn.execute(stmt)
    await _sqlite_conn.commit()
