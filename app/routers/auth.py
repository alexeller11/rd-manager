from fastapi import APIRouter

router = APIRouter()

DEFAULT_USER = {"id": 1, "username": "alexeller", "is_admin": True}

@router.post("/login")
async def login():
    return {"access_token": "no-auth", "token_type": "bearer", **DEFAULT_USER}

@router.get("/me")
async def me():
    return DEFAULT_USER

@router.get("/check")
async def check_has_users():
    return {"has_users": True}

@router.post("/logout")
async def logout():
    return {"ok": True}
