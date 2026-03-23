"""OAuth2 RD Station — apenas Marketing."""
import os
import json
import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from app.auth_core import save_mkt_token, MKT_CLIENT_ID, MKT_CLIENT_SECRET, RD_TOKEN_URL

router = APIRouter()

# Constrói a URL de redirecionamento dinamicamente
# Prioridade: RD_REDIRECT_URI > RAILWAY_STATIC_URL > fallback para localhost
REDIRECT_URI = os.environ.get(
    "RD_REDIRECT_URI",
    ("https://" + os.environ.get("RAILWAY_STATIC_URL") if os.environ.get("RAILWAY_STATIC_URL") else "http://localhost:8000") + "/oauth/callback"
)
RD_AUTH_URL = "https://api.rd.services/auth/dialog"


def _success_html(client_id: int, product: str) -> str:
    return f"""<!DOCTYPE html><html><head><title>Conectado!</title>
<style>body{{font-family:Arial,sans-serif;text-align:center;padding:50px;}}
h1{{color:#28a745;}}a{{color:#007bff;}}</style></head>
<body><h1>Conectado com sucesso!</h1>
<p>Cliente #{client_id} — {product}</p>
<p>Feche esta aba e clique em <strong>Sincronizar RD</strong> no app.</p>
<a href="/">Ir para o app</a></body></html>"""


def _error_html(msg: str) -> str:
    return f"""<!DOCTYPE html><html><head><title>Erro</title>
<style>body{{font-family:Arial,sans-serif;text-align:center;padding:50px;}}
h1{{color:#dc3545;}}a{{color:#007bff;}}</style></head>
<body><h1>Erro na autenticação</h1>
<p>{msg}</p><a href="/">Voltar para o app</a></body></html>"""


@router.get("/authorize/{client_id}")
async def start_oauth(client_id: int):
    if not MKT_CLIENT_ID:
        return HTMLResponse(_error_html("RD_CLIENT_ID não configurado nas variáveis de ambiente do Railway."))
    url = (
        f"{RD_AUTH_URL}?response_type=code"
        f"&client_id={MKT_CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
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

    client_id = int(state.split(":")[-1]) if state and ":" in state else 0

    async with httpx.AsyncClient(timeout=15.0) as http:
        r = await http.post(RD_TOKEN_URL, json={
            "client_id": MKT_CLIENT_ID,
            "client_secret": MKT_CLIENT_SECRET,
            "redirect_uri": REDIRECT_URI,
            "code": code,
            "grant_type": "authorization_code"
        })

    if r.status_code != 200:
        return HTMLResponse(_error_html(f"Erro ao trocar code: HTTP {r.status_code}"))

    data = r.json()
    if "error" in data:
        return HTMLResponse(_error_html(f"Erro: {json.dumps(data)}"))

    access_token  = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")

    if client_id and access_token:
        await save_mkt_token(client_id, access_token, refresh_token)

    return HTMLResponse(_success_html(client_id, "RD Marketing"))
