import logging
import os
import secrets
import time

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, RedirectResponse

from app.auth_core import MKT_CLIENT_ID, MKT_CLIENT_SECRET, RD_TOKEN_URL, save_mkt_token
from app.core.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter()
settings = get_settings()

RD_AUTH_URL = "https://api.rd.services/auth/dialog"

# fix #1: estado CSRF agora guarda (client_id, timestamp) com TTL de 10 minutos.
# Em multi-instância usar Redis; aqui é suficiente para single-instance.
_CSRF_TTL = 600  # segundos
_pending_states: dict[str, tuple[int, float]] = {}


def _cleanup_expired_states() -> None:
    """Remove estados CSRF expirados — chamado a cada callback."""
    now = time.monotonic()
    expired = [k for k, (_, ts) in _pending_states.items() if now - ts > _CSRF_TTL]
    for k in expired:
        _pending_states.pop(k, None)
    if expired:
        logger.debug("OAuth: %d estados CSRF expirados removidos", len(expired))


def get_redirect_uri() -> str:
    explicit = getattr(settings, "rd_redirect_uri", None) or os.getenv("RD_REDIRECT_URI")
    if explicit:
        return explicit

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url:
        return f"{render_url.rstrip('/')}/oauth/callback"

    origins = getattr(settings, "allowed_origins", None) or []
    if origins:
        base = origins[0] if origins[0] != "*" else "http://localhost:8000"
        return f"{base.rstrip('/')}/oauth/callback"

    return "http://localhost:8000/oauth/callback"


def _html(title: str, msg: str, ok: bool = True) -> str:
    color = "#10b981" if ok else "#ef4444"
    return f"""
    <html>
      <head>
        <title>{title}</title>
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <style>
            body {{ font-family: 'Inter', sans-serif; background: #030708; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; }}
            .card {{ background: #0b0f13; padding: 40px; border-radius: 16px; border: 1px solid #1e2933; text-align: center; max-width: 400px; box-shadow: 0 10px 40px rgba(0,0,0,0.5); }}
            h1 {{ color: {color}; margin-top: 0; font-size: 24px; }}
            p {{ color: #94a3b8; line-height: 1.6; }}
            .btn {{ display: inline-block; margin-top: 20px; padding: 10px 20px; background: #10b981; color: #000; text-decoration: none; border-radius: 8px; font-weight: 600; }}
        </style>
      </head>
      <body>
        <div class="card">
          <h1>{title}</h1>
          <p>{msg}</p>
          <p>Você já pode fechar esta aba e voltar ao sistema.</p>
        </div>
      </body>
    </html>
    """


@router.get("/authorize/{client_id}")
async def start_oauth(client_id: int):
    if not MKT_CLIENT_ID:
        return HTMLResponse(_html("Erro", "RD_CLIENT_ID não configurado.", ok=False), status_code=500)

    # Gera token CSRF e associa ao client_id com timestamp
    csrf_token = secrets.token_urlsafe(24)
    _pending_states[csrf_token] = (client_id, time.monotonic())

    redirect_uri = get_redirect_uri()
    state = f"{client_id}:{csrf_token}"

    url = (
        f"{RD_AUTH_URL}"
        f"?response_type=code"
        f"&client_id={MKT_CLIENT_ID}"
        f"&redirect_uri={redirect_uri}"
        f"&state={state}"
    )

    logger.info("OAuth iniciado para cliente %s", client_id)
    return RedirectResponse(url)


@router.get("/callback")
async def oauth_callback(
    code: str | None = None,
    state: str | None = None,
    error: str | None = None,
):
    # Limpa estados expirados a cada callback
    _cleanup_expired_states()

    if error:
        logger.warning("OAuth erro retornado pela RD: %s", error)
        return HTMLResponse(_html("Erro na conexão RD", f"Erro retornado pela RD: {error}", ok=False), status_code=400)

    if not code:
        return HTMLResponse(_html("Erro na conexão RD", "Code não recebido.", ok=False), status_code=400)

    # Valida state com CSRF
    try:
        parts = (state or "").split(":", 1)
        if len(parts) != 2:
            raise ValueError("state malformado")
        client_id = int(parts[0])
        csrf_token = parts[1]
    except Exception:
        return HTMLResponse(_html("Erro na conexão RD", "State inválido.", ok=False), status_code=400)

    # fix #1: valida TTL — rejeita estados expirados
    entry = _pending_states.pop(csrf_token, None)
    if entry is None:
        logger.warning("OAuth CSRF falhou: csrf=%s não encontrado", csrf_token[:8])
        return HTMLResponse(_html("Erro na conexão RD", "Token CSRF inválido ou expirado.", ok=False), status_code=400)

    expected_client_id, issued_at = entry
    if expected_client_id != client_id:
        logger.warning("OAuth CSRF client_id mismatch: esperado=%s recebido=%s", expected_client_id, client_id)
        return HTMLResponse(_html("Erro na conexão RD", "Token CSRF inválido.", ok=False), status_code=400)

    if time.monotonic() - issued_at > _CSRF_TTL:
        logger.warning("OAuth CSRF expirado para cliente %s", client_id)
        return HTMLResponse(_html("Erro na conexão RD", "Sessão de autorização expirada. Tente novamente.", ok=False), status_code=400)

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
        # fix #2: loga o detalhe internamente, exibe mensagem genérica para o usuário
        logger.error("OAuth falha ao trocar token (status %s): %s", response.status_code, response.text[:500])
        return HTMLResponse(
            _html("Erro na conexão RD", "Falha ao conectar com a RD Station. Tente novamente ou contate o suporte.", ok=False),
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

    logger.info("OAuth concluído com sucesso para cliente %s", client_id)
    return HTMLResponse(_html("RD conectada com sucesso", f"Cliente #{client_id} autenticado."))
