import os
import asyncpg
import aiosqlite
from typing import Any, Optional

from app.core.settings import get_settings

settings = get_settings()

_pool: Optional[asyncpg.Pool] = None
_sqlite_conn: Optional[aiosqlite.Connection] = None


# =========================
# DETECÇÃO DE BANCO
# =========================

def _is_postgres() -> bool:
    return settings.database_url.startswith("postgresql")


# =========================
# INIT
# =========================

async def init_db():
    global _pool, _sqlite_conn

    if _is_postgres():
        _pool = await asyncpg.create_pool(settings.database_url)
        print("✅ PostgreSQL inicializado com sucesso.")
    else:
        _sqlite_conn = await aiosqlite.connect("rd_manager.db")
        await _sqlite_conn.execute("PRAGMA foreign_keys = ON;")
        print("✅ SQLite inicializado com sucesso.")


async def close_db():
    global _pool, _sqlite_conn

    if _pool:
        await _pool.close()

    if _sqlite_conn:
        await _sqlite_conn.close()


# =========================
# EXECUTE
# =========================

async def db_execute(query: str, *args):
    if _is_postgres():
        async with _pool.acquire() as conn:
            return await conn.execute(query, *args)
    else:
        cursor = await _sqlite_conn.execute(query, args)
        await _sqlite_conn.commit()
        return cursor


# =========================
# FETCH ONE (🔥 faltava isso)
# =========================

async def db_fetch_one(query: str, *args) -> Optional[dict]:
    if _is_postgres():
        async with _pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None
    else:
        cursor = await _sqlite_conn.execute(query, args)
        row = await cursor.fetchone()
        if row is None:
            return None
        return {k[0]: row[i] for i, k in enumerate(cursor.description)}


# =========================
# FETCH ALL
# =========================

async def db_fetch_all(query: str, *args) -> list[dict]:
    if _is_postgres():
        async with _pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]
    else:
        cursor = await _sqlite_conn.execute(query, args)
        rows = await cursor.fetchall()
        return [
            {k[0]: row[i] for i, k in enumerate(cursor.description)}
            for row in rows
        ]
