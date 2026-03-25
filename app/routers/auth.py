from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.auth_core import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    get_current_user,
    verify_password,
)
from app.database import db_fetch_one

router = APIRouter()


@router.post("/login")
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = await db_fetch_one(
        "SELECT id, username, password FROM users WHERE username = $1",
        form_data.username,
    )

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user["password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuário ou senha inválidos",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_minutes=ACCESS_TOKEN_EXPIRE_MINUTES,
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
    }


@router.get("/me")
async def read_users_me(current_user: dict = Depends(get_current_user)):
    return current_user


@router.get("/check")
async def check_has_users():
    user = await db_fetch_one("SELECT id FROM users LIMIT 1")
    return {"has_users": bool(user)}


@router.post("/logout")
async def logout():
    return {"ok": True}
