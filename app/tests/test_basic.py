from httpx import AsyncClient, ASGITransport
from fastapi import status
import pytest

from app.main import app


@pytest.mark.anyio
async def test_health_ok():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        resp = await ac.get("/health")

    # Pode ser 200 (ok) ou 503 (degraded) dependendo do estado do banco nos testes
    assert resp.status_code in {status.HTTP_200_OK, status.HTTP_503_SERVICE_UNAVAILABLE}
    data = resp.json()
    assert data.get("status") in {"ok", "degraded"}


@pytest.mark.anyio
async def test_auth_login_invalid_credentials():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # OAuth2PasswordRequestForm espera form-data, não JSON
        payload = {"username": "invalid", "password": "wrong"}
        resp = await ac.post("/api/auth/login", data=payload)

    assert resp.status_code == status.HTTP_401_UNAUTHORIZED
