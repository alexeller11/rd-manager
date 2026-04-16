import pytest
from httpx import AsyncClient
from fastapi import status

from app.main import app


@pytest.mark.anyio
async def test_clients_requires_auth():
    """GET /api/clients sem token deve retornar 401 ou 403."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/clients/")
    assert resp.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_agency_overview_requires_auth():
    """GET /api/agency/overview sem token deve retornar 401 ou 403."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/api/agency/overview")
    assert resp.status_code in {status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN}


@pytest.mark.anyio
async def test_health_returns_200():
    """GET /health deve retornar 200 sempre."""
    async with AsyncClient(app=app, base_url="http://test") as ac:
        resp = await ac.get("/health")
    assert resp.status_code == status.HTTP_200_OK
    assert "status" in resp.json()
