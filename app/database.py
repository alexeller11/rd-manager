"""
Camada de banco de dados unificada.
Usa PostgreSQL (produção) via DATABASE_URL ou SQLite (fallback local).
Toda a lógica de dual-driver fica aqui — routers não precisam saber qual banco estão usando.
"""
import os
import json
import asyncio
import aiosqlite
import asyncpg
from contextlib import asynccontextmanager

DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///./rd_manager.db")

_pg_pool: asyncpg.Pool | None = None
_pg_lock = asyncio.Lock()


# ─── Pool PostgreSQL (lazy init) ────────────────────────────────────────────

async def get_pg_pool() -> asyncpg.Pool:
    global _pg_pool
    if _pg_pool is None:
        async with _pg_lock:
            if _pg_pool is None:
                _pg_pool = await asyncpg.create_pool(DATABASE_URL, min_size=1, max_size=10)
    return _pg_pool


def _is_sqlite() -> bool:
    return DATABASE_URL.startswith("sqlite")


# ─── Helpers de query ────────────────────────────────────────────────────────

async def db_fetchone(query: str, *args) -> dict | None:
    """Retorna uma linha como dict ou None."""
    if _is_sqlite():
        sq = query.replace("$1", "?").replace("$2", "?").replace("$3", "?") \
                  .replace("$4", "?").replace("$5", "?").replace("$6", "?") \
                  .replace("$7", "?").replace("$8", "?").replace("$9", "?").replace("$10", "?").replace("$11", "?")
        path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sq, args) as cur:
                row = await cur.fetchone()
                return dict(row) if row else None
    else:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(query, *args)
            return dict(row) if row else None


async def db_fetchall(query: str, *args) -> list[dict]:
    """Retorna lista de dicts."""
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(sq, args) as cur:
                return [dict(r) for r in await cur.fetchall()]
    else:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(query, *args)
            return [dict(r) for r in rows]


async def db_execute(query: str, *args) -> None:
    """Executa sem retorno."""
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(path) as db:
            await db.execute(sq, args)
            await db.commit()
    else:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.execute(query, *args)


async def db_fetchval(query: str, *args):
    """Executa e retorna o primeiro valor (útil para RETURNING id)."""
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        # Remove RETURNING clause for sqlite — we use lastrowid
        sq_noret = sq.split(" RETURNING ")[0] if " RETURNING " in sq.upper() else sq
        path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(path) as db:
            cur = await db.execute(sq_noret, args)
            await db.commit()
            return cur.lastrowid
    else:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            return await conn.fetchval(query, *args)


async def db_executemany(query: str, args_list: list) -> None:
    """Executa em batch."""
    if _is_sqlite():
        sq = _to_sqlite_params(query)
        path = DATABASE_URL.replace("sqlite:///", "")
        async with aiosqlite.connect(path) as db:
            await db.executemany(sq, args_list)
            await db.commit()
    else:
        pool = await get_pg_pool()
        async with pool.acquire() as conn:
            await conn.executemany(query, args_list)


def _to_sqlite_params(query: str) -> str:
    """Converte $1..$N para ? no SQLite."""
    import re
    return re.sub(r'\$\d+', '?', query)


def parse_json_field(val) -> dict | list:
    """Parseia campo JSON de qualquer driver (string, dict, Record asyncpg)."""
    if val is None:
        return {}
    if isinstance(val, (dict, list)):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    try:
        return json.loads(json.dumps(dict(val)))
    except Exception:
        return {}


# ─── Schema ─────────────────────────────────────────────────────────────────

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
    data JSONB,
    snapshot_type TEXT DEFAULT 'full_sync',
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS crm_snapshots (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    data JSONB,
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
    flow_data JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE TABLE IF NOT EXISTS weekly_analyses (
    id SERIAL PRIMARY KEY,
    client_id INTEGER REFERENCES clients(id) ON DELETE CASCADE,
    result TEXT,
    week_ref TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
"""


async def init_db():
    """Inicializa o banco e cria as tabelas com tratamento de erro."""
    try:
        if _is_sqlite():
            path = DATABASE_URL.replace("sqlite:///", "")
            async with aiosqlite.connect(path) as db:
                await db.executescript(SCHEMA_SQLITE)
                await db.commit()
            print("✅ SQLite initialized")
        else:
            pool = await get_pg_pool()
            async with pool.acquire() as conn:
                for stmt in SCHEMA_PG.strip().split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        await conn.execute(stmt)
            print("✅ PostgreSQL initialized")
    except Exception as e:
        print(f"⚠️ Erro ao inicializar banco de dados: {e}")
        print("A aplicação continuará rodando, mas funcionalidades de persistência podem falhar.")
