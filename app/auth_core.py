import os
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import get_settings
from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval

settings = get_settings()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

JWT_ALGORITHM = "HS256"
RD_TOKEN_URL = "https://api.rd.services/auth/token"

MKT_CLIENT_ID = getattr(settings, "rd_client_id", None) or os.getenv("RD_CLIENT_ID") or os.getenv("RD_CRM_CLIENT_ID")
MKT_CLIENT_SECRET = getattr(settings, "rd_client_secret", None) or os.getenv("RD_CLIENT_SECRET") or os.getenv("RD_CRM_CLIENT_SECRET")
RD_REDIRECT_URI = getattr(settings, "rd_redirect_uri", None) or os.getenv("RD_REDIRECT_URI")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _admin_username() -> str:
    return getattr(settings, "admin_username", None) or os.getenv("ADMIN_USERNAME", "admin")


def _admin_password() -> str:
    return getattr(settings, "admin_password", None) or os.getenv("ADMIN_PASSWORD", "admin123456789")


def _secret_key() -> str:
    return getattr(settings, "secret_key", None) or os.getenv("SECRET_KEY", "changeme_super_secret_key_1234567890")


def _token_expire_minutes() -> int:
    value = getattr(settings, "token_expire_minutes", None) or os.getenv("TOKEN_EXPIRE_MINUTES", "1440")
    try:
        return int(value)
    except Exception:
        return 1440


async def ensure_auth_tables():
    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS admin_users (
            id SERIAL PRIMARY KEY,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    await db_execute(
        """
        CREATE TABLE IF NOT EXISTS rd_credentials (
            client_id INTEGER PRIMARY KEY,
            access_token TEXT,
            refresh_token TEXT,
            expires_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            account_data JSONB
        )
        """
    )

    # garante colunas em bases antigas
    await db_execute("ALTER TABLE rd_credentials ADD COLUMN IF NOT EXISTS access_token TEXT")
    await db_execute("ALTER TABLE rd_credentials ADD COLUMN IF NOT EXISTS refresh_token TEXT")
    await db_execute("ALTER TABLE rd_credentials ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")
    await db_execute("ALTER TABLE rd_credentials ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ")
    await db_execute("ALTER TABLE rd_credentials ADD COLUMN IF NOT EXISTS account_data JSONB")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, password_hash: str) -> bool:
    return pwd_context.verify(plain_password, password_hash)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = _now() + (expires_delta or timedelta(minutes=_token_expire_minutes()))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, _secret_key(), algorithm=JWT_ALGORITHM)


async def ensure_admin_exists():
    await ensure_auth_tables()

    username = _admin_username()
    password = _admin_password()

    row = await db_fetch_one(
        "SELECT id, username, password_hash FROM admin_users WHERE username = $1",
        username,
    )

    if row:
        return

    await db_execute(
        """
        INSERT INTO admin_users (username, password_hash, created_at, updated_at)
        VALUES ($1, $2, $3, $4)
        """,
        username,
        hash_password(password),
        _now(),
        _now(),
    )


async def authenticate_admin(username: str, password: str) -> Optional[dict]:
    await ensure_auth_tables()

    row = await db_fetch_one(
        "SELECT id, username, password_hash FROM admin_users WHERE username = $1",
        username,
    )

    if not row:
        return None

    if not verify_password(password, row["password_hash"]):
        return None

    return {
        "id": row["id"],
        "username": row["username"],
    }


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    token = credentials.credentials

    try:
        payload = jwt.decode(token, _secret_key(), algorithms=[JWT_ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise HTTPException(status_code=401, detail="Invalid token")
        return {"username": username}
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


async def require_admin(user: dict = Depends(get_current_user)):
    return user


async def clear_mkt_credentials(client_id: int):
    await ensure_auth_tables()
    await db_execute("DELETE FROM rd_credentials WHERE client_id = $1", client_id)


async def save_mkt_token(
    client_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: int = 3600,
    account_data: Optional[dict] = None,
):
    await ensure_auth_tables()

    expires_at = _now() + timedelta(seconds=int(expires_in or 3600))

    await db_execute(
        """
        INSERT INTO rd_credentials (
            client_id,
            access_token,
            refresh_token,
            expires_at,
            updated_at,
            account_data
        )
        VALUES ($1, $2, $3, $4, $5, $6)
        ON CONFLICT (client_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            updated_at = EXCLUDED.updated_at,
            account_data = EXCLUDED.account_data
        """,
        client_id,
        access_token,
        refresh_token,
        expires_at,
        _now(),
        account_data,
    )


async def _get_mkt_credentials(client_id: int) -> Optional[dict]:
    await ensure_auth_tables()

    return await db_fetch_one(
        """
        SELECT client_id, access_token, refresh_token, expires_at, updated_at, account_data
        FROM rd_credentials
        WHERE client_id = $1
        """,
        client_id,
    )


async def refresh_mkt_token(client_id: int) -> str:
    creds = await _get_mkt_credentials(client_id)

    if not creds or not creds.get("refresh_token"):
        raise HTTPException(status_code=400, detail="Cliente sem refresh token RD")

    if not MKT_CLIENT_ID or not MKT_CLIENT_SECRET:
        raise HTTPException(status_code=500, detail="RD client id/secret não configurados")

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "refresh_token": creds["refresh_token"],
        "grant_type": "refresh_token",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(RD_TOKEN_URL, data=payload)

    if response.status_code >= 400:
        raise HTTPException(
            status_code=500,
            detail=f"Falha ao renovar token RD: {response.text[:500]}",
        )

    data = response.json()

    access_token = (data.get("access_token") or "").strip()
    refresh_token = (data.get("refresh_token") or creds["refresh_token"] or "").strip()
    expires_in = int(data.get("expires_in") or 3600)

    if not access_token:
        raise HTTPException(status_code=500, detail="RD retornou access_token vazio")

    await save_mkt_token(
        client_id=client_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        account_data=creds.get("account_data"),
    )

    return access_token


async def get_valid_mkt_token(client_id: int) -> str:
    creds = await _get_mkt_credentials(client_id)

    if not creds or not creds.get("access_token"):
        raise HTTPException(status_code=400, detail="Cliente sem token RD")

    expires_at = creds.get("expires_at")
    if expires_at and isinstance(expires_at, datetime):
        if expires_at <= (_now() + timedelta(minutes=5)):
            return await refresh_mkt_token(client_id)

    return creds["access_token"]


async def migrate_plaintext_rd_credentials():
    """
    Migra tokens antigos guardados em clients.rd_token / rd_refresh_token.
    Não quebra se a tabela/colunas antigas não existirem.
    """
    await ensure_auth_tables()

    try:
        rows = await db_fetch_all(
            """
            SELECT id, rd_token, rd_refresh_token
            FROM clients
            """
        )
    except Exception:
        return

    for row in rows or []:
        access_token = (row.get("rd_token") or "").strip()
        refresh_token = (row.get("rd_refresh_token") or "").strip()

        if not access_token:
            continue

        existing = await _get_mkt_credentials(row["id"])
        if existing and existing.get("access_token"):
            continue

        await save_mkt_token(
            client_id=row["id"],
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=3600,
            account_data=None,
        )
