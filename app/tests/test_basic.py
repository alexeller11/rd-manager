from httpx import AsyncClient
from fastapi import status

from app.main import app


async def test_health_ok():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/health")

    assert resp.status_code == status.HTTP_200_OK
    data = resp.json()
    assert data.get("status") in {"ok", "degraded"}


async def test_auth_login_invalid_credentials():
    async with AsyncClient(app=app, base_url="http://test") as ac:
        payload = {"username": "invalid", "password": "wrong"}
        resp = await ac.post("/api/auth/login", json=payload)

    assert resp.status_code in {status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED}
