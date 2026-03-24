from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt

from app.core.settings import get_settings
from app.database import db_execute, db_fetch_one

settings = get_settings()
security = HTTPBearer()


# =========================
# JWT
# =========================

def create_access_token(data: dict, expires_minutes: int = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or settings.token_expire_minutes
    )

    to_encode.update({"exp": expire})

    return jwt.encode(to_encode, settings.secret_key, algorithm="HS256")


def verify_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido",
        )


# =========================
# AUTH DEPENDENCIES
# =========================

async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    token = credentials.credentials
    payload = verify_token(token)
    return payload


def require_admin(user=Depends(get_current_user)):
    if user.get("username") != settings.admin_username:
        raise HTTPException(status_code=403, detail="Acesso negado")
    return user


# =========================
# ADMIN
# =========================

async def ensure_admin_exists():
    query = "SELECT id FROM users WHERE username = $1"
    user = await db_fetch_one(query, settings.admin_username)

    if user:
        return

    insert = """
    INSERT INTO users (username, password, created_at)
    VALUES ($1, $2, $3)
    """

    await db_execute(
        insert,
        settings.admin_username,
        settings.admin_password,
        datetime.now(timezone.utc),
    )


# =========================
# RD TOKENS
# =========================

async def save_mkt_token(
    client_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: Optional[int] = 3600,
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in or 3600)

    query = """
    INSERT INTO rd_credentials (
        client_id,
        access_token,
        refresh_token,
        expires_at,
        updated_at
    )
    VALUES ($1, $2, $3, $4, $5)
    ON CONFLICT (client_id)
    DO UPDATE SET
        access_token = EXCLUDED.access_token,
        refresh_token = EXCLUDED.refresh_token,
        expires_at = EXCLUDED.expires_at,
        updated_at = EXCLUDED.updated_at
    """

    await db_execute(
        query,
        client_id,
        access_token,
        refresh_token,
        expires_at,
        now,
    )


# =========================
# GET RD CREDENTIALS (🔥 NOVO FIX)
# =========================

async def get_rd_credentials(client_id: int) -> Optional[dict]:
    query = """
    SELECT access_token, refresh_token, expires_at
    FROM rd_credentials
    WHERE client_id = $1
    """

    return await db_fetch_one(query, client_id)


# =========================
# MIGRAÇÃO
# =========================

async def migrate_plaintext_rd_credentials():
    rows = await db_fetch_one("""
        SELECT id, rd_token, rd_refresh_token
        FROM clients
        WHERE rd_token IS NOT NULL
    """)

    if not rows:
        return

    if not isinstance(rows, list):
        rows = [rows]

    for row in rows:
        await save_mkt_token(
            row["id"],
            row.get("rd_token") or "",
            row.get("rd_refresh_token") or "",
        )


# =========================
# CLEAR CRM CREDENTIALS
# =========================

async def clear_crm_credentials(client_id: int):
    query = """
    UPDATE rd_credentials
    SET
        access_token = NULL,
        refresh_token = NULL,
        expires_at = NULL,
        updated_at = $2
    WHERE client_id = $1
    """

    await db_execute(
        query,
        client_id,
        datetime.now(timezone.utc),
    )


# =========================
# CLEAR MKT CREDENTIALS
# =========================

async def clear_mkt_credentials(client_id: int):
    query = """
    UPDATE rd_credentials
    SET
        access_token = NULL,
        refresh_token = NULL,
        expires_at = NULL,
        updated_at = $2
    WHERE client_id = $1
    """

    await db_execute(
        query,
        client_id,
        datetime.now(timezone.utc),
    )
