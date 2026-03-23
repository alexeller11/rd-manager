"""
Autenticação real com JWT + bcrypt.
- Tokens JWT com expiração configurável
- Password hash via bcrypt
- Usuário admin criado automaticamente no primeiro boot
- get_current_user como dependency do FastAPI
"""
import os
import traceback
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
import bcrypt

from app.database import db_execute, db_fetchone, db_fetchval

# ─── Configurações ────────────────────────────────────────────────────────────

SECRET_KEY = os.environ.get("SECRET_KEY", "TROQUE_ISTO_POR_UMA_CHAVE_SEGURA_EM_PRODUCAO")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.environ.get("TOKEN_EXPIRE_MINUTES", "1440"))  # 24h

ADMIN_USER = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASS = os.environ.get("ADMIN_PASSWORD", "admin123")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ─── RD Station OAuth ─────────────────────────────────────────────────────────

import httpx
import asyncio

RD_TOKEN_URL = "https://api.rd.services/auth/token"
MKT_CLIENT_ID = os.environ.get("RD_CLIENT_ID", "")
MKT_CLIENT_SECRET = os.environ.get("RD_CLIENT_SECRET", "")

_refresh_locks: dict[int, asyncio.Lock] = {}
# Cache simples de token em memória para evitar calls desnecessárias à API RD
_token_cache: dict[int, str] = {}


# ─── Funções de senha ─────────────────────────────────────────────────────────

def hash_password(password: str) -> str:
    """Hash de senha usando bcrypt diretamente."""
    # bcrypt tem limite de 72 bytes, então truncamos
    pwd_bytes = password[:72].encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')


def verify_password(plain: str, hashed: str) -> bool:
    """Verifica senha contra hash bcrypt."""
    try:
        pwd_bytes = plain[:72].encode('utf-8')
        hashed_bytes = hashed.encode('utf-8') if isinstance(hashed, str) else hashed
        return bcrypt.checkpw(pwd_bytes, hashed_bytes)
    except Exception:
        return False


# ─── JWT ─────────────────────────────────────────────────────────────────────

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
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
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception

    user = await db_fetchone("SELECT id, username, is_admin FROM users WHERE username = $1", username)
    if user is None:
        raise credentials_exception
    return user


# ─── Criação do admin no boot ─────────────────────────────────────────────────

async def ensure_admin_exists():
    """Cria o usuário admin padrão se não existir nenhum usuário."""
    existing = await db_fetchone("SELECT id FROM users LIMIT 1")
    if not existing:
        hashed = hash_password(ADMIN_PASS)
        await db_execute(
            "INSERT INTO users (username, password_hash, is_admin) VALUES ($1, $2, $3)",
            ADMIN_USER, hashed, True
        )


# ─── Tokens RD Station ───────────────────────────────────────────────────────

async def get_tokens_from_db(client_id: int) -> dict:
    row = await db_fetchone(
        "SELECT rd_token, rd_refresh_token, rd_crm_token FROM clients WHERE id = $1",
        client_id
    )
    return row or {}


async def save_mkt_token(client_id: int, access_token: str, refresh_token: str):
    _token_cache.pop(client_id, None)  # invalida cache
    # Garantir que os tokens não sejam None
    acc = (access_token or "").strip()
    ref = (refresh_token or "").strip()
    
    # Para PostgreSQL, usamos datetime.utcnow() diretamente em vez de string ISO
    # O driver asyncpg cuida da conversão para TIMESTAMPTZ
    from app.database import _is_sqlite
    now = datetime.utcnow() if not _is_sqlite() else datetime.utcnow().isoformat()
    
    await db_execute(
        "UPDATE clients SET rd_token=$1, rd_refresh_token=$2, updated_at=$3 WHERE id=$4",
        acc, ref, now, client_id
    )


async def _refresh_mkt_token(client_id: int) -> str:
    tokens = await get_tokens_from_db(client_id)
    refresh_tok = (tokens.get("rd_refresh_token") or "").strip()
    if not refresh_tok:
        return ""

    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            r = await http.post(RD_TOKEN_URL, json={
                "client_id": MKT_CLIENT_ID,
                "client_secret": MKT_CLIENT_SECRET,
                "refresh_token": refresh_tok,
                "grant_type": "refresh_token"
            })
            if r.status_code == 200:
                data = r.json()
                new_acc = data.get("access_token", "")
                new_ref = data.get("refresh_token", refresh_tok)
                if new_acc:
                    await save_mkt_token(client_id, new_acc, new_ref)
                    _token_cache[client_id] = new_acc
                return new_acc
            # log silencioso
            await _log_error(client_id, "/auth/token", "POST", f"Refresh falhou: HTTP {r.status_code}")
        except Exception as e:
            await _log_error(client_id, "/auth/token", "POST", e)
    return ""


async def get_valid_mkt_token(client_id: int) -> str:
    """
    Retorna token válido. Usa cache em memória para evitar verificação a cada request.
    Só bate na API RD quando o token expira (401).
    """
    # Usa cache se disponível
    if client_id in _token_cache:
        return _token_cache[client_id]

    tokens = await get_tokens_from_db(client_id)
    token = (tokens.get("rd_token") or "").strip()
    if not token:
        return ""

    # Verifica token rapidamente
    if client_id not in _refresh_locks:
        _refresh_locks[client_id] = asyncio.Lock()

    async with httpx.AsyncClient(timeout=15.0) as http:
        try:
            # Tenta um endpoint universal para validar o token (Contatos)
            # Se falhar com 404 ou 403, pode ser que o usuário não tenha permissão, mas o token ainda é válido para outros fins.
            r = await http.get(
                "https://api.rd.services/platform/contacts",
                headers={"Authorization": f"Bearer {token}"},
                params={"page": 1, "page_size": 1}
            )
            
            # 200 OK ou 404/403 em endpoints específicos podem significar que o token é válido, mas sem acesso a este recurso.
            # No entanto, se o token estiver expirado, ele retornará 401.
            if r.status_code == 200:
                _token_cache[client_id] = token
                return token
            
            # Se o token expirou (401), tenta refresh obrigatoriamente
            if r.status_code == 401:
                async with _refresh_locks[client_id]:
                    # Tenta novamente o cache (pode ter sido atualizado por outro processo enquanto esperava o lock)
                    if client_id in _token_cache and _token_cache[client_id] != token:
                        return _token_cache[client_id]
                        
                    new_token = await _refresh_mkt_token(client_id)
                    if new_token:
                        _token_cache[client_id] = new_token
                        return new_token
                    else:
                        # Se o refresh falhou, o token está morto
                        await db_execute("UPDATE clients SET rd_token='', rd_refresh_token='' WHERE id=$1", client_id)
                        _token_cache.pop(client_id, None)
                        return ""
            
            # Se for 403 (Proibido), o token é válido mas não tem escopo para este endpoint.
            # Não limpamos o token aqui, pois ele pode ser útil para outros endpoints (ex: emails).
            if r.status_code == 403:
                _token_cache[client_id] = token
                return token

            # Erro 400 (Bad Request) costuma indicar token revogado definitivamente.
            if r.status_code == 400:
                await db_execute("UPDATE clients SET rd_token='', rd_refresh_token='' WHERE id=$1", client_id)
                _token_cache.pop(client_id, None)
                return ""
                
        except Exception as e:
            await _log_error(client_id, "check_token", "GET", e)

    return token


async def _log_error(client_id, endpoint, method, error):
    try:
        await db_execute(
            "INSERT INTO error_logs (client_id, endpoint, method, error_message, stack_trace) VALUES ($1,$2,$3,$4,$5)",
            client_id, endpoint, method, str(error), traceback.format_exc()
        )
    except Exception:
        pass
