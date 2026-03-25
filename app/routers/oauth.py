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

    domain = settings.allowed_origins[0] if settings.allowed_origins else "http://localhost:8000"
    return f"{domain.rstrip('/')}/oauth/callback"


def _success_html(client_id: int, product: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><title>Conectado!</title></head>
<body style="font-family:Arial;text-align:center;padding:50px;">
    <h1 style="color:#28a745;">Conectado com sucesso!</h1>
    <p>Cliente #{client_id} — {product}</p>
    <p>Feche esta aba e volte para o sistema.</p>
    <a href="/">Ir para o app</a>
</body>
</html>
"""


def _error_html(msg: str) -> str:
    return f"""
<!DOCTYPE html>
<html>
<head><title>Erro</title></head>
<body style="font-family:Arial;text-align:center;padding:50px;">
    <h1 style="color:#dc3545;">Erro na autenticação</h1>
    <p>{msg}</p>
    <a href="/">Voltar</a>
</body>
</html>
"""


@router.get("/authorize/{client_id}")
async def start_oauth(client_id: int):
    if not MKT_CLIENT_ID:
        return HTMLResponse(_error_html("RD_CLIENT_ID não configurado."))

    redirect_uri = get_redirect_uri()
    url = (
        f"{RD_AUTH_URL}?response_type=code"
        f"&client_id={MKT_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state=mkt:{client_id}"
        f"&scope=contacts-read+landing-pages-read+emails-read+segmentations-read"
    )
    return RedirectResponse(url)


@router.get("/callback")
async def oauth_callback(code: str = None, state: str = None, error: str = None):
    if error:
        return HTMLResponse(_error_html(f"RD Station retornou erro: {error}"))
    if not code:
        return HTMLResponse(_error_html("Code não recebido."))

    try:
        client_id = int(state.split(":")[-1]) if state and ":" in state else 0
    except Exception:
        client_id = 0

    payload = {
        "client_id": MKT_CLIENT_ID,
        "client_secret": MKT_CLIENT_SECRET,
        "redirect_uri": get_redirect_uri(),
        "code": code,
        "grant_type": "authorization_code",
    }

    async with httpx.AsyncClient(timeout=20.0) as http:
        response = await http.post(RD_TOKEN_URL, data=payload)

    if response.status_code != 200:
        try:
            err_data = response.json()
            err_msg = err_data.get("error_description", err_data.get("error", f"HTTP {response.status_code}"))
        except Exception:
            err_msg = f"HTTP {response.status_code}: {response.text[:200]}"
        return HTMLResponse(_error_html(f"Erro na troca do token: {err_msg}"))

    data = response.json()
    if "error" in data:
        return HTMLResponse(_error_html(json.dumps(data)))

    access_token = data.get("access_token", "").strip()
    refresh_token = data.get("refresh_token", "").strip()
    expires_in = data.get("expires_in", 3600)

    if not client_id or not access_token:
        return HTMLResponse(_error_html("Falha na identificação do cliente ou token vazio."))

    await save_mkt_token(client_id, access_token, refresh_token, expires_in)
    return HTMLResponse(_success_html(client_id, "RD Marketing"))
