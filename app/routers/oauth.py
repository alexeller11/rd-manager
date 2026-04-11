import os

import httpx
from fastapi import APIRouter
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth_core import MKT_CLIENT_ID, MKT_CLIENT_SECRET, RD_TOKEN_URL, save_mkt_token
from app.core.settings import get_settings

router = APIRouter()
settings = get_settings()

RD_AUTH_URL = "https://api.rd.services/auth/dialog"


def get_redirect_uri() -> str:
    explicit = getattr(settings, "rd_redirect_uri", None) or os.getenv("RD_REDIRECT_URI")
    if explicit:
        return explicit

    origins = getattr(settings, "allowed_origins", None) or []
    if origins:
        return origins[0].rstrip("/") + "/oauth/callback"

    return "http://localhost:8000/oauth/callback"


def _html(title: str, msg: str, ok: bool = True) -> str:
    color = "#22a06b" if ok else "#d64c4c"
    return f"""
    <html>
      <head><title>{title}</title></head>
      <body style="font-family:Arial;padding:40px;text-align:center;background:#f7f7f7;">
        <div style="max-width:620px;margin:0 auto;background:#fff;padding:32px;border-radius:18px;border:1px solid #ddd;">
          <h1 style="color:{color};margin-bottom:12px;">{title}</h1>
          <p style="font-size:16px;line-height:1.5;color:#333;">{msg}</p>
          <p style="color:#666;">Você já pode fechar esta aba e voltar ao sistema.</p>
        </div>
      </body>
    </html>
    """


@router.get("/authorize/{client_id}")
async def start_oauth(client_id: int):
    if not MKT_CLIENT_ID:
        return HTMLResponse(_html("Erro", "RD_CLIENT_ID não configurado.", ok=False), status_code=500)

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
async def oauth_callback(code: str | None = None, state: str | None = None, error: str | None = None):
    if error:
        return HTMLResponse(_html("Erro na conexão RD", f"Erro retornado pela RD: {error}", ok=False), status_code=400)

    if not code:
        return HTMLResponse(_html("Erro na conexão RD", "Code não recebido.", ok=False), status_code=400)

    try:
        client_id = int(state)
    except Exception:
        return HTMLResponse(_html("Erro na conexão RD", "State inválido.", ok=False), status_code=400)

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "redirect_uri": get_redirect_uri(),
        "code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.post(RD_TOKEN_URL, data=payload)

    if response.status_code >= 400:
        return HTMLResponse(
            _html("Erro na conexão RD", f"Falha ao trocar token: {response.text[:500]}", ok=False),
            status_code=500,
        )

    data = response.json()
    access_token = (data.get("access_token") or "").strip()
    refresh_token = (data.get("refresh_token") or "").strip()
    expires_in = int(data.get("expires_in") or 3600)

    if not access_token:
        return HTMLResponse(_html("Erro na conexão RD", "A RD retornou token vazio.", ok=False), status_code=500)

    await save_mkt_token(
        client_id=client_id,
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=expires_in,
        account_data=data,
    )

    return HTMLResponse(_html("RD conectada com sucesso", f"Cliente #{client_id} autenticado."))
