from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import jwt
from passlib.context import CryptContext

from app.core.settings import get_settings
from app.database import db_execute, db_fetch_one

settings = get_settings()
security = HTTPBearer()

# =========================
# CONFIG GLOBAL
# =========================

ACCESS_TOKEN_EXPIRE_MINUTES = settings.token_expire_minutes

# 🔥 OAUTH RD
MKT_CLIENT_ID = settings.rd_client_id
MKT_CLIENT_SECRET = settings.rd_client_secret
RD_TOKEN_URL = "https://api.rd.services/auth/token"

# =========================
# PASSWORD
# =========================

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return pwd_context.verify(plain_password, hashed_password)


# =========================
# JWT
# =========================

def create_access_token(data: dict, expires_minutes: int = None) -> str:
    to_encode = data.copy()

    expire = datetime.now(timezone.utc) + timedelta(
        minutes=expires_minutes or ACCESS_TOKEN_EXPIRE_MINUTES
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

    await db_execute(
        """
        INSERT INTO users (username, password, created_at)
        VALUES ($1, $2, $3)
        """,
        settings.admin_username,
        hash_password(settings.admin_password),
        datetime.now(timezone.utc),
    )


# =========================
# TOKENS RD
# =========================

async def save_mkt_token(
    client_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: Optional[int] = 3600,
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in or 3600)

    await db_execute(
        """
        INSERT INTO rd_credentials (
            client_id, access_token, refresh_token, expires_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (client_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            updated_at = EXCLUDED.updated_at
        """,
        client_id,
        access_token,
        refresh_token,
        expires_at,
        now,
    )


async def save_crm_token(
    client_id: int,
    access_token: str,
    refresh_token: str,
    expires_in: Optional[int] = 3600,
):
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(seconds=expires_in or 3600)

    await db_execute(
        """
        INSERT INTO rd_credentials (
            client_id, access_token, refresh_token, expires_at, updated_at
        )
        VALUES ($1, $2, $3, $4, $5)
        ON CONFLICT (client_id)
        DO UPDATE SET
            access_token = EXCLUDED.access_token,
            refresh_token = EXCLUDED.refresh_token,
            expires_at = EXCLUDED.expires_at,
            updated_at = EXCLUDED.updated_at
        """,
        client_id,
        access_token,
        refresh_token,
        expires_at,
        now,
    )


# =========================
# GET
# =========================

async def get_rd_credentials(client_id: int) -> Optional[dict]:
    return await db_fetch_one(
        """
        SELECT access_token, refresh_token, expires_at
        FROM rd_credentials
        WHERE client_id = $1
        """,
        client_id,
    )


# =========================
# CLEAR
# =========================

async def clear_crm_credentials(client_id: int):
    await db_execute(
        """
        UPDATE rd_credentials
        SET access_token = NULL,
            refresh_token = NULL,
            expires_at = NULL,
            updated_at = $2
        WHERE client_id = $1
        """,
        client_id,
        datetime.now(timezone.utc),
    )


async def clear_mkt_credentials(client_id: int):
    await db_execute(
        """
        UPDATE rd_credentials
        SET access_token = NULL,
            refresh_token = NULL,
            expires_at = NULL,
            updated_at = $2
        WHERE client_id = $1
        """,
        client_id,
        datetime.now(timezone.utc),
    )


# =========================
# MIGRAÇÃO
# =========================

async def migrate_plaintext_rd_credentials():
    row = await db_fetch_one("""
        SELECT id, rd_token, rd_refresh_token
        FROM clients
        WHERE rd_token IS NOT NULL
    """)

    if not row:
        return

    await save_mkt_token(
        row["id"],
        row.get("rd_token") or "",
        row.get("rd_refresh_token") or "",
    )
import httpx


# =========================
# TOKEN VALIDATION RD (FINAL FIX)
# =========================

async def refresh_mkt_token(client_id: int, refresh_token: str) -> dict:
    """
    Faz refresh do token na RD Station
    """

    async with httpx.AsyncClient() as client:
        response = await client.post(
            RD_TOKEN_URL,
            data={
                "grant_type": "refresh_token",
                "client_id": MKT_CLIENT_ID,
                "client_secret": MKT_CLIENT_SECRET,
                "refresh_token": refresh_token,
            },
        )

    if response.status_code != 200:
        raise Exception("Erro ao renovar token RD")

    data = response.json()

    await save_mkt_token(
        client_id,
        data["access_token"],
        data.get("refresh_token", refresh_token),
        data.get("expires_in", 3600),
    )

    return data


async def get_valid_mkt_token(client_id: int) -> str:
    """
    Retorna token válido, renovando se necessário
    """

    creds = await get_rd_credentials(client_id)

    if not creds:
        raise Exception("Cliente não possui credenciais RD")

    access_token = creds.get("access_token")
    refresh_token = creds.get("refresh_token")
    expires_at = creds.get("expires_at")

    # Se não tiver expiração, força refresh
    if not expires_at:
        new = await refresh_mkt_token(client_id, refresh_token)
        return new["access_token"]

    now = datetime.now(timezone.utc)

    # Se expirou
    if expires_at < now:
        new = await refresh_mkt_token(client_id, refresh_token)
        return new["access_token"]

    return access_token
