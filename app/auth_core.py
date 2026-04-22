from datetime import datetime, timedelta, timezone
from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.settings import get_settings
from app.database import db_execute, db_fetch_all, db_fetch_one, db_fetchval, using_postgres, db_fetchone, db_fetchall

settings = get_settings()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

pwd_context = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto",
)

ALGORITHM = "HS256"

MKT_CLIENT_ID = (settings.rd_client_id or "").strip()
MKT_CLIENT_SECRET = (settings.rd_client_secret or "").strip()
RD_TOKEN_URL = "https://api.rd.services/auth/token"

# Pool HTTP reutilizável para chamadas de auth (token exchange / refresh)
_AUTH_HTTP_CLIENT: Optional[httpx.AsyncClient] = None


def _get_auth_http_client() -> httpx.AsyncClient:
    global _AUTH_HTTP_CLIENT
    if _AUTH_HTTP_CLIENT is None or _AUTH_HTTP_CLIENT.is_closed:
        _AUTH_HTTP_CLIENT = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=5.0),
            limits=httpx.Limits(
                max_keepalive_connections=5,
                max_connections=10,
                keepalive_expiry=30.0,
            ),
        )
    return _AUTH_HTTP_CLIENT


# Cache in-memory de tokens RD
# Estrutura: { client_id: {"token": str, "expires_at": datetime} }
# TTL conservador: expira 60s antes do token real para garantir margem.
_token_cache: dict[int, dict] = {}
_CACHE_MARGIN = timedelta(seconds=60)


def _cache_put(client_id: int, token: str, expires_at: datetime | None) -> None:
    if not token:
        return
    if expires_at is None:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=3600)
    _token_cache[client_id] = {"token": token, "expires_at": expires_at - _CACHE_MARGIN}


def _cache_get(client_id: int) -> str | None:
    entry = _token_cache.get(client_id)
    if not entry:
        return None
    if entry["expires_at"] <= datetime.now(timezone.utc):
        _token_cache.pop(client_id, None)
        return None
    return entry["token"]


def _cache_invalidate(client_id: int) -> None:
    _token_cache.pop(client_id, None)


async def save_mkt_token(
    client_id: int,
    access_token: str,
    refresh_token: str = "",
    expires_in: int = 3600,
    account_data: dict | None = None,
):
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(int(expires_in or 3600), 60))

    if using_postgres():
        await db_execute(
            """
            INSERT INTO rd_credentials (
                client_id,
                access_token,
                refresh_token,
                expires_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, NOW())
            ON CONFLICT (client_id)
            DO UPDATE SET
                access_token = EXCLUDED.access_token,
                refresh_token = EXCLUDED.refresh_token,
                expires_at = EXCLUDED.expires_at,
                updated_at = NOW()
            """,
            client_id,
            (access_token or "").strip(),
            (refresh_token or "").strip(),
            expires_at,
        )
    else:
        await db_execute(
            """
            INSERT INTO rd_credentials (
                client_id,
                access_token,
                refresh_token,
                expires_at,
                updated_at
            )
            VALUES ($1, $2, $3, $4, CURRENT_TIMESTAMP)
            ON CONFLICT (client_id)
            DO UPDATE SET
                access_token = excluded.access_token,
                refresh_token = excluded.refresh_token,
                expires_at = excluded.expires_at,
                updated_at = CURRENT_TIMESTAMP
            """,
            client_id,
            (access_token or "").strip(),
            (refresh_token or "").strip(),
            expires_at.isoformat(),
        )

    # compatibilidade com código legado que ainda lê clients.rd_token
    await db_execute(
        """
        UPDATE clients
        SET rd_token = $2
        WHERE id = $1
        """,
        client_id,
        (access_token or "").strip(),
    )

    _cache_put(client_id, (access_token or "").strip(), expires_at)

    return {
        "client_id": client_id,
        "saved": True,
        "expires_at": expires_at.isoformat(),
        "has_account_data": bool(account_data),
    }


def _parse_expires_at(value) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value
    if isinstance(value, str):
        try:
            normalized = value.replace("Z", "+00:00")
            parsed = datetime.fromisoformat(normalized)
            if parsed.tzinfo is None:
                return parsed.replace(tzinfo=timezone.utc)
            return parsed
        except ValueError:
            return None
    return None


def _normalize_password_for_bcrypt(password: str) -> str:
    if password is None:
        return ""
    if not isinstance(password, str):
        password = str(password)
    raw = password.encode("utf-8")
    if len(raw) <= 72:
        return password
    trimmed = raw[:72]
    while True:
        try:
            return trimmed.decode("utf-8")
        except UnicodeDecodeError:
            trimmed = trimmed[:-1]
            if not trimmed:
                return ""


def hash_password(password: str) -> str:
    normalized = _normalize_password_for_bcrypt(password)
    return pwd_context.hash(normalized)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    normalized = _normalize_password_for_bcrypt(plain_password)
    return pwd_context.verify(normalized, hashed_password)


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.token_expire_minutes)
    )
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.secret_key, algorithm=ALGORITHM)
    return encoded_jwt


async def get_admin_by_username(username: str):
    return await db_fetch_one(
        """
        SELECT id, username, password_hash, created_at
        FROM admins
        WHERE username = $1
        """,
        username,
    )


async def ensure_admin_exists():
    existing = await db_fetch_one(
        """
        SELECT id, username
        FROM admins
        WHERE username = $1
        """,
        settings.admin_username,
    )
    if existing:
        return existing
    password_hash = hash_password(settings.admin_password)
    await db_execute(
        """
        INSERT INTO admins (username, password_hash)
        VALUES ($1, $2)
        """,
        settings.admin_username,
        password_hash,
    )
    return await get_admin_by_username(settings.admin_username)


async def authenticate_admin(username: str, password: str):
    user = await get_admin_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return {"id": user["id"], "username": user["username"]}


async def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
        username: str | None = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = await get_admin_by_username(username)
    if user is None:
        raise credentials_exception
    return {"id": user["id"], "username": user["username"]}


async def get_valid_mkt_token(client_id: int) -> str:
    cached = _cache_get(client_id)
    if cached:
        return cached

    row = await db_fetch_one(
        """
        SELECT access_token, refresh_token, expires_at
        FROM rd_credentials
        WHERE client_id = $1
        """,
        client_id,
    )

    if row and row.get("access_token"):
        expires_at = _parse_expires_at(row.get("expires_at"))
        expires_soon = (
            expires_at is not None
            and expires_at <= datetime.now(timezone.utc) + timedelta(seconds=30)
        )
        if expires_soon and row.get("refresh_token"):
            refreshed = await refresh_mkt_token(client_id)
            if refreshed:
                return refreshed

        token = row["access_token"]
        _cache_put(client_id, token, expires_at)
        return token

    # fallback: coluna legada clients.rd_token
    client = await db_fetch_one(
        """
        SELECT rd_token
        FROM clients
        WHERE id = $1
        """,
        client_id,
    )
    if client and client.get("rd_token"):
        _cache_put(client_id, client["rd_token"], None)
        return client["rd_token"]

    raise RuntimeError("Cliente sem token RD conectado.")


async def refresh_mkt_token(client_id: int) -> str | None:
    _cache_invalidate(client_id)

    row = await db_fetch_one(
        """
        SELECT refresh_token
        FROM rd_credentials
        WHERE client_id = $1
        """,
        client_id,
    )
    refresh_token = (row or {}).get("refresh_token")
    if not refresh_token:
        return None

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    # Usa pool reutilizável em vez de AsyncClient avulso
    http = _get_auth_http_client()
    response = await http.post(RD_TOKEN_URL, data=payload)

    if response.status_code >= 400:
        return None

    data = response.json()
    access_token = (data.get("access_token") or "").strip()
    if not access_token:
        return None

    await save_mkt_token(
        client_id=client_id,
        access_token=access_token,
        refresh_token=(data.get("refresh_token") or refresh_token),
        expires_in=int(data.get("expires_in") or 3600),
        account_data=data,
    )
    return access_token


async def migrate_plaintext_rd_credentials():
    rows = await db_fetch_all(
        """
        SELECT id, access_token, refresh_token
        FROM rd_credentials
        """
    ) or []
    return rows
