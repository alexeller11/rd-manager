from fastapi import APIRouter, HTTPException, Depends
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel
from app.auth_core import (
    verify_password, create_access_token, hash_password,
    get_current_user
)
from app.database import db_fetchone, db_execute, db_fetchval

router = APIRouter()


class UserCreate(BaseModel):
    username: str
    password: str


@router.post("/login")
async def login(form: OAuth2PasswordRequestForm = Depends()):
    user = await db_fetchone(
        "SELECT id, username, password_hash, is_admin FROM users WHERE username = $1",
        form.username
    )
    if not user or not verify_password(form.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Usuário ou senha incorretos")

    token = create_access_token({"sub": user["username"]})
    return {
        "access_token": token,
        "token_type": "bearer",
        "username": user["username"],
        "is_admin": bool(user.get("is_admin"))
    }


@router.get("/me")
async def me(user=Depends(get_current_user)):
    return {"id": user["id"], "username": user["username"], "is_admin": bool(user.get("is_admin"))}


@router.get("/check")
async def check_has_users():
    row = await db_fetchone("SELECT id FROM users LIMIT 1")
    return {"has_users": row is not None}


@router.post("/logout")
async def logout():
    # JWT é stateless; o frontend simplesmente descarta o token.
    return {"ok": True}


@router.post("/register")
async def register(data: UserCreate, current_user=Depends(get_current_user)):
    """Cria novo usuário — apenas admins podem criar outros usuários."""
    if not current_user.get("is_admin"):
        raise HTTPException(status_code=403, detail="Apenas admins podem criar usuários")

    existing = await db_fetchone("SELECT id FROM users WHERE username = $1", data.username)
    if existing:
        raise HTTPException(status_code=409, detail="Usuário já existe")

    hashed = hash_password(data.password)
    user_id = await db_fetchval(
        "INSERT INTO users (username, password_hash) VALUES ($1, $2) RETURNING id",
        data.username, hashed
    )
    return {"id": user_id, "username": data.username}
