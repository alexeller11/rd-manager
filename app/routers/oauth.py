import json

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth_core import MKT_CLIENT_ID, MKT_CLIENT_SECRET, RD_TOKEN_URL, save_mkt_token
from app.core.settings import get_settings

router = APIRouter()
settings = get_settings()

RD_AUTH_URL = "https://api.rd.services/auth/dialog"


def get_redirect_uri() -> str:
    if settings.rd_redirect_uri:
        return settings.rd_redirect_uri

    if settings.allowed_origins:
        return settings.allowed_origins[0].rstrip("/") + "/oauth/callback"

    return "http://localhost:8000/oauth/callback"


def _success_html(client_id: int) -> str:
    return f"""
    <html>
      <head><title>RD conectada</title></head>
      <body style="font-family:Arial;padding:40px;text-align:center;">
        <h1 style="color:#22a06b;">RD conectada com sucesso</h1>
        <p>Cliente #{client_id} autenticado.</p>
        <p>Feche esta aba e volte para a plataforma.</p>
      </body>
    </html>
    """


def _error_html(msg: str) -> str:
    return f"""
    <html>
      <head><title>Erro</title></head>
      <body style="font-family:Arial;padding:40px;text-align:center;">
        <h1 style="color:#d84b4b;">Erro na conexão RD</h1>
        <p>{msg}</p>
      </body>
    </html>
    """


@router.get("/authorize/{client_id}")
async def start_oauth(client_id: int):
    if not MKT_CLIENT_ID:
        return HTMLResponse(_error_html("RD_CLIENT_ID não configurado."), status_code=500)

    redirect_uri = get_redirect_uri()

    url = (
        f"{RD_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={MKT_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={client_id}"
    )

    return RedirectResponse(url)


@router.get("/callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return HTMLResponse(_error_html(f"Erro retornado pela RD: {error}"), status_code=400)

    if not code:
        return HTMLResponse(_error_html("Code não recebido."), status_code=400)

    try:
        client_id = int(state)
    except Exception:
        return HTMLResponse(_error_html("State inválido."), status_code=400)

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "redirect_uri": get_redirect_uri(),
        "code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(RD_TOKEN_URL, data=payload)

    if response.status_code != 200:
        return HTMLResponse(
            _error_html(f"Falha ao trocar token: {response.text[:500]}"),
            status_code=500,
        )

    data = response.json()

    access_token = data.get("access_token", "").strip()
    refresh_token = data.get("refresh_token", "").strip()
    expires_in = data.get("expires_in", 3600)

    if not access_token:
        return HTMLResponse(
            _error_html("A RD retornou token vazio."),
            status_code=500,
        )

    await save_mkt_token(
        client_id=client_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
    )

    return HTMLResponse(_success_html(client_id))
