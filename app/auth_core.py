"""
Autenticação, autorização e gerenciamento seguro de credenciais RD.
"""
import json
import traceback
from datetime import datetime, timedelta, timezone
from typing import Optional

import bcrypt
import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt

from app.core.settings import get_settings
from app.database import db_execute, db_fetchall, db_fetchone

settings = get_settings()

SECRET_KEY = settings.secret_key
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = settings.token_expire_minutes
ADMIN_USER = settings.admin_username
ADMIN_PASS = settings.admin_password

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

RD_TOKEN_URL = "https://api.rd.services/auth/token"
MKT_CLIENT_ID = settings.rd_client_id
MKT_CLIENT_SECRET = settings.rd_client_secret

_cipher = Fernet(settings.token_encryption_key.encode("utf-8"))


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    pwd_bytes = password[:72].encode("utf-8")
    return bcrypt.hashpw(pwd_bytes, bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(plain[:72].encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode["exp"] = expire
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Token inválido ou expirado",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username = payload.get("sub")
        if not username:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db_fetchone(
        "SELECT id, username, is_admin FROM users WHERE username = $1",
        username,
    )
    if not user:
        raise credentials_exception
    return user


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Acesso restrito a administradores")
    return current_user


async def ensure_admin_exists() -> None:
    existing = await db_fetchone("SELECT id FROM users LIMIT 1")
    if existing:
        return
    await db_execute(
        "INSERT INTO users (username, password_hash, is_admin) VALUES ($1, $2, $3)",
        ADMIN_USER,
        hash_password(ADMIN_PASS),
        True,
    )


def encrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    return _cipher.encrypt(value.encode("utf-8")).decode("utf-8")


def decrypt_secret(value: str | None) -> str:
    if not value:
        return ""
    try:
        return _cipher.decrypt(value.encode("utf-8")).decode("utf-8")
    except InvalidToken:
        return ""
    except Exception:
        return ""


async def _upsert_credentials(
    client_id: int,
    encrypted_mkt_token: str | None = None,
    encrypted_mkt_refresh_token: str | None = None,
    encrypted_crm_token: str | None = None,
    token_status: str | None = None,
    touch_refresh: bool = False,
) -> None:
    current = await db_fetchone("SELECT * FROM rd_credentials WHERE client_id = $1", client_id)
    now = utcnow().isoformat()

    if current:
        await db_execute(
            """
            UPDATE rd_credentials
               SET encrypted_mkt_token = COALESCE($1, encrypted_mkt_token),
                   encrypted_mkt_refresh_token = COALESCE($2, encrypted_mkt_refresh_token),
                   encrypted_crm_token = COALESCE($3, encrypted_crm_token),
                   token_status = COALESCE($4, token_status),
                   last_refresh_at = CASE WHEN $5 THEN $6 ELSE last_refresh_at END,
                   updated_at = $6
             WHERE client_id = $7
            """,
            encrypted_mkt_token,
            encrypted_mkt_refresh_token,
            encrypted_crm_token,
            token_status,
            touch_refresh,
            now,
            client_id,
        )
        return

    await db_execute(
        """
        INSERT INTO rd_credentials
            (client_id, encrypted_mkt_token, encrypted_mkt_refresh_token, encrypted_crm_token, token_status, last_refresh_at, updated_at)
        VALUES ($1, $2, $3, $4, $5, $6, $6)
        """,
        client_id,
        encrypted_mkt_token,
        encrypted_mkt_refresh_token,
        encrypted_crm_token,
        token_status or "unknown",
        now if touch_refresh else None,
    )


async def save_mkt_token(client_id: int, access_token: str, refresh_token: str = "") -> None:
    await _upsert_credentials(
        client_id=client_id,
        encrypted_mkt_token=encrypt_secret(access_token),
        encrypted_mkt_refresh_token=encrypt_secret(refresh_token) if refresh_token else None,
        token_status="valid",
        touch_refresh=bool(refresh_token),
    )


async def save_crm_token(client_id: int, crm_token: str) -> None:
    await _upsert_credentials(
        client_id=client_id,
        encrypted_crm_token=encrypt_secret(crm_token),
        token_status="valid",
    )


async def clear_mkt_credentials(client_id: int) -> None:
    await db_execute(
        """
        UPDATE rd_credentials
           SET encrypted_mkt_token = '',
               encrypted_mkt_refresh_token = '',
               token_status = 'cleared',
               updated_at = $1
         WHERE client_id = $2
        """,
        utcnow().isoformat(),
        client_id,
    )


async def clear_crm_credentials(client_id: int) -> None:
    await db_execute(
        """
        UPDATE rd_credentials
           SET encrypted_crm_token = '',
               updated_at = $1
         WHERE client_id = $2
        """,
        utcnow().isoformat(),
        client_id,
    )


async def get_rd_credentials(client_id: int) -> dict:
    cred = await db_fetchone("SELECT * FROM rd_credentials WHERE client_id = $1", client_id)
    if cred:
        return {
            "rd_token": decrypt_secret(cred.get("encrypted_mkt_token")),
            "rd_refresh_token": decrypt_secret(cred.get("encrypted_mkt_refresh_token")),
            "rd_crm_token": decrypt_secret(cred.get("encrypted_crm_token")),
            "token_status": cred.get("token_status") or "unknown",
            "last_validated_at": cred.get("last_validated_at"),
            "last_refresh_at": cred.get("last_refresh_at"),
        }

    legacy = await db_fetchone(
        "SELECT rd_token, rd_refresh_token, rd_crm_token FROM clients WHERE id = $1",
        client_id,
    )
    if not legacy:
        return {}

    return {
        "rd_token": legacy.get("rd_token") or "",
        "rd_refresh_token": legacy.get("rd_refresh_token") or "",
        "rd_crm_token": legacy.get("rd_crm_token") or "",
        "token_status": "legacy",
        "last_validated_at": None,
        "last_refresh_at": None,
    }


async def migrate_plaintext_rd_credentials() -> None:
    rows = await db_fetchall(
        """
        SELECT id, rd_token, rd_refresh_token, rd_crm_token
          FROM clients
         WHERE COALESCE(rd_token, '') <> ''
            OR COALESCE(rd_refresh_token, '') <> ''
            OR COALESCE(rd_crm_token, '') <> ''
        """
    )
    for row in rows:
        client_id = row["id"]
        if row.get("rd_token") or row.get("rd_refresh_token"):
            await save_mkt_token(client_id, row.get("rd_token") or "", row.get("rd_refresh_token") or "")
        if row.get("rd_crm_token"):
            await save_crm_token(client_id, row["rd_crm_token"])

        await db_execute(
            """
            UPDATE clients
               SET rd_token = '',
                   rd_refresh_token = '',
                   rd_crm_token = '',
                   updated_at = $1
             WHERE id = $2
            """,
            utcnow().isoformat(),
            client_id,
        )


async def _log_error(client_id: int | None, endpoint: str, method: str, error: str) -> None:
    try:
        await db_execute(
            """
            INSERT INTO error_logs (client_id, endpoint, method, error_message, stack_trace)
            VALUES ($1, $2, $3, $4, $5)
            """,
            client_id,
            endpoint,
            method,
            error,
            traceback.format_exc(),
        )
    except Exception:
        pass


async def get_valid_mkt_token(client_id: int) -> str:
    creds = await get_rd_credentials(client_id)
    token = (creds.get("rd_token") or "").strip()
    if token:
        return token

    refresh = (creds.get("rd_refresh_token") or "").strip()
    if refresh:
        return await refresh_mkt_token(client_id)
    return ""


async def refresh_mkt_token(client_id: int) -> str:
    creds = await get_rd_credentials(client_id)
    refresh_token = (creds.get("rd_refresh_token") or "").strip()
    if not refresh_token:
        return ""

    if not MKT_CLIENT_ID or not MKT_CLIENT_SECRET:
        await _log_error(client_id, "/auth/token", "POST", "RD_CLIENT_ID/RD_CLIENT_SECRET ausentes")
        return ""

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }

    try:
        async with httpx.AsyncClient(timeout=20.0) as http:
            response = await http.post(RD_TOKEN_URL, data=payload)

        if response.status_code != 200:
            await _log_error(client_id, "/auth/token", "POST", f"Refresh falhou: {response.status_code} | {response.text[:300]}")
            return ""

        data = response.json()
        new_access = data.get("access_token", "").strip()
        new_refresh = data.get("refresh_token", refresh_token).strip()
        if not new_access:
            await _log_error(client_id, "/auth/token", "POST", "Refresh retornou sem access_token")
            return ""

        await save_mkt_token(client_id, new_access, new_refresh)
        return new_access

    except Exception as e:
        await _log_error(client_id, "/auth/token", "POST", str(e))
        return ""
