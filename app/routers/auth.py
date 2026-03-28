from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordRequestForm

from app.auth_core import (
    authenticate_admin,
    create_access_token,
    ensure_admin_exists,
    get_current_user,
)

router = APIRouter()


@router.post("/login")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    await ensure_admin_exists()

    user = await authenticate_admin(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Usuário ou senha inválidos")

    access_token = create_access_token(
        {"sub": user["username"]},
        expires_delta=timedelta(days=1),
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "username": user["username"],
    }


@router.get("/me")
async def me(current_user: dict = Depends(get_current_user)):
    return {
        "ok": True,
        "user": current_user,
    }
