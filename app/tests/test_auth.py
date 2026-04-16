import pytest
import pytest_anyio
from httpx import AsyncClient, ASGITransport
from unittest.mock import AsyncMock, patch
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-ci-only-32chars")
os.environ.setdefault("ADMIN_PASSWORD", "admin123")
os.environ.setdefault("GROQ_API_KEY", "fake")
os.environ.setdefault("RD_CLIENT_ID", "fake")
os.environ.setdefault("RD_CLIENT_SECRET", "fake")
os.environ.setdefault("RD_REDIRECT_URI", "http://localhost/oauth/callback")

from app.main import app


@pytest.fixture(scope="module")
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_health_check():
    """Health check deve retornar status ok."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.database.db_fetchval", new_callable=AsyncMock, return_value=1):
            resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["version"] == "4.0.0"


@pytest.mark.anyio
async def test_login_sem_credenciais():
    """Login sem corpo deve retornar 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/auth/login", json={})
    assert resp.status_code == 422


@pytest.mark.anyio
async def test_login_credenciais_invalidas():
    """Login com credenciais erradas deve retornar 401 ou 422."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        with patch("app.auth_core.init_db", new_callable=AsyncMock):
            resp = await client.post("/api/auth/login", json={"username": "wrong", "password": "wrong"})
    assert resp.status_code in (401, 422, 400)


@pytest.mark.anyio
async def test_rota_protegida_sem_token():
    """Rota de clientes sem token deve retornar 401 ou 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/clients")
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_rota_protegida_token_invalido():
    """Token inválido deve retornar 401 ou 403."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/clients", headers={"Authorization": "Bearer token-invalido"})
    assert resp.status_code in (401, 403)


@pytest.mark.anyio
async def test_docs_disponiveis():
    """Docs Swagger devem estar acessíveis."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/docs")
    assert resp.status_code == 200
