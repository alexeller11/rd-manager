import json
import logging
from typing import Any, Optional

import aiosqlite
import asyncpg

from app.core.settings import get_settings

logger = logging.getLogger(__name__)
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
    import asyncio
    for attempt in range(3):
        try:
            global _pg_pool, _sqlite_conn

            if using_postgres():
                database_url = _normalize_database_url(settings.database_url)
                if database_url.startswith("postgresql+asyncpg://"):
                    database_url = database_url.replace("postgresql+asyncpg://", "postgresql://", 1)

                _pg_pool = await asyncpg.create_pool(
                    dsn=database_url,
                    min_size=1,
                    # fix: aumentado de 2 para 5 para suportar requisições concorrentes em produção
                    max_size=5,
                    ssl='require' if 'render.com' in database_url or settings.app_env == 'production' else None,
                    command_timeout=60,
                )
                logger.info("✅ PostgreSQL inicializado com sucesso.")
            else:
                _sqlite_conn = await aiosqlite.connect("rd_manager.db")
                _sqlite_conn.row_factory = aiosqlite.Row
                logger.info("✅ SQLite inicializado com sucesso.")

            await init_schema()
            logger.info("Banco de dados e schema inicializados com sucesso.")
            return
        except Exception as e:
            logger.error("Erro ao inicializar o banco de dados (tentativa %d/3): %s", attempt + 1, e)
            await asyncio.sleep(5)

    # fix: levanta RuntimeError em vez de retornar None silenciosamente
    raise RuntimeError(
        "Falha ao inicializar o banco de dados após 3 tentativas. Verifique DATABASE_URL e conexão com o banco."
    )


async def init_schema():
    if using_postgres():
        async with _pg_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS leads (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    email TEXT UNIQUE NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
    else:
        await _sqlite_conn.execute("""
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)


async def db_execute(query: str, *args) -> None:
    if using_postgres():
        async with _pg_pool.acquire() as conn:
            await conn.execute(query, *args)
    else:
        await _sqlite_conn.execute(query, *args)


async def db_fetch_one(query: str, *args) -> Optional[dict]:
    if using_postgres():
        async with _pg_pool.acquire() as conn:
            result = await conn.fetchrow(query, *args)
            return dict(result) if result else None
    else:
        cursor = await _sqlite_conn.execute(query, *args)
        row = await cursor.fetchone()
        return dict(row) if row else None


async def db_fetch_all(query: str, *args) -> list[dict]:
    if using_postgres():
        async with _pg_pool.acquire() as conn:
            result = await conn.fetch(query, *args)
            return [dict(row) for row in result]
    else:
        cursor = await _sqlite_conn.execute(query, *args)
        rows = await cursor.fetchall()
        return [dict(row) for row in rows]


async def db_fetchval(query: str, *args) -> Any:
    if using_postgres():
        async with _pg_pool.acquire() as conn:
            result = await conn.fetchval(query, *args)
            return result
    else:
        cursor = await _sqlite_conn.execute(query, *args)
        row = await cursor.fetchone()
        return row[0] if row else None
