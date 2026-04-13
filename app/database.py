import json
from typing import Any, Optional

import aiosqlite
import asyncpg

from app.core.settings import get_settings

settings = get_settings()

_pg_pool: Optional[asyncpg.Pool] = None
_sqlite_conn: Optional[aiosqlite.Connection] = None


def _normalize_database_url(url: str) -> str:
    url = (url or "").strip()
    if url.startswith("postgres://"):
        return "postgresql://" + url[len("postgres://"):]
    return url


def using_postgres() -> bool:
    db_url = _normalize_database_url(settings.database_url)
    return db_url.startswith(("postgresql://", "postgresql+asyncpg://"))


async def init_db():
    global _pg_pool, _sqlite_conn

    if using_postgres():
        database_url = _normalize_database_url(settings.database_url)
        if database_url.startswith("postgresql+asyncpg://"):
            database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

        _pg_pool = await asyncpg.create_pool(
            dsn=database_url,
            min_size=1,
            max_size=2,
            ssl='require' if 'render.com' in database_url or settings.app_env == 'production' else None,
            command_timeout=60
        )
        print("✅ PostgreSQL inicializado com sucesso.")
    else:
        _sqlite_conn = await aiosqlite.connect("rd_manager.db")
        _sqlite_conn.row_factory = aiosqlite.Row
        print("✅ SQLite inicializado com sucesso.")

    await init_schema()


async def close_db():
    global _pg_pool, _sqlite_conn

    if _pg_pool is not None:
        await _pg_pool.close()
        _pg_pool = None

    if _sqlite_conn is not None:
        await _sqlite_conn.close()
        _sqlite_conn = None


def _json_safe(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


async def db_execute(query: str, *args):
    if using_postgres():
        assert _pg_pool is not None, "PostgreSQL pool não inicializado"
        async with _pg_pool.acquire() as conn:
            return await conn.execute(query, *args)

    assert _sqlite_conn is not None, "SQLite connection não inicializada"
    cursor = await _sqlite_conn.execute(query, tuple(_json_safe(arg) for arg in args))
    await _sqlite_conn.commit()
    return cursor


async def db_fetch_one(query: str, *args):
    if using_postgres():
        assert _pg_pool is not None, "PostgreSQL pool não inicializado"
        async with _pg_pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None

    assert _sqlite_conn is not None, "SQLite connection não inicializada"
    cursor = await _sqlite_conn.execute(query, tuple(_json_safe(arg) for arg in args))
    row = await cursor.fetchone()
    return dict(row) if row else None


async def db_fetch_all(query: str, *args):
    if using_postgres():
        assert _pg_pool is not None, "PostgreSQL pool não inicializado"
        async with _pg_pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(row) for row in rows]

    assert _sqlite_conn is not None, "SQLite connection não inicializada"
    cursor = await _sqlite_conn.execute(query, tuple(_json_safe(arg) for arg in args))
    rows = await cursor.fetchall()
    return [dict(row) for row in rows]


async def db_fetchval(query: str, *args):
    if using_postgres():
        assert _pg_pool is not None, "PostgreSQL pool não inicializado"
        async with _pg_pool.acquire() as conn:
            return await conn.fetchval(query, *args)

    assert _sqlite_conn is not None, "SQLite connection não inicializada"
    cursor = await _sqlite_conn.execute(query, tuple(_json_safe(arg) for arg in args))
    row = await cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, aiosqlite.Row):
        values = list(row)
        return values[0] if values else None
    return row[0] if row else None


async def init_schema():
    if using_postgres():
        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                website TEXT,
                segment TEXT,
                description TEXT,
                rd_token TEXT,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS rd_credentials (
                id SERIAL PRIMARY KEY,
                client_id INTEGER UNIQUE REFERENCES clients(id) ON DELETE CASCADE,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TIMESTAMPTZ,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id SERIAL PRIMARY KEY,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )

    else:
        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                website TEXT,
                segment TEXT,
                description TEXT,
                rd_token TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS rd_credentials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                client_id INTEGER UNIQUE,
                access_token TEXT,
                refresh_token TEXT,
                expires_at TEXT,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (client_id) REFERENCES clients(id) ON DELETE CASCADE
            )
            """
        )

        await db_execute(
            """
            CREATE TABLE IF NOT EXISTS admins (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
            """
        )


def parse_json_field(value: Any, default: Any = None) -> Any:
    if value is None:
        return {} if default is None else default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, (bytes, bytearray)):
        value = value.decode("utf-8", errors="ignore")
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return {} if default is None else default
        try:
            return json.loads(text)
        except Exception:
            return {} if default is None else default
    return {} if default is None else default


async def db_fetchone(query: str, *args):
    return await db_fetch_one(query, *args)


async def db_fetchall(query: str, *args):
    return await db_fetch_all(query, *args)
