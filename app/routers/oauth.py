"""OAuth2 RD Station — apenas Marketing."""
import os
import json
import httpx
from fastapi import APIRouter
from fastapi.responses import RedirectResponse, HTMLResponse
from app.auth_core import save_mkt_token, MKT_CLIENT_ID, MKT_CLIENT_SECRET, RD_TOKEN_URL

router = APIRouter()

# Constrói a URL de redirecionamento dinamicamente
# Prioridade: RD_REDIRECT_URI > RAILWAY_PUBLIC_DOMAIN > RAILWAY_STATIC_URL > fallback para localhost
def get_redirect_uri():
    if manual := os.environ.get("RD_REDIRECT_URI"):
        return manual
    
    # Railway fornece RAILWAY_PUBLIC_DOMAIN ou RAILWAY_STATIC_URL
    domain = os.environ.get("RAILWAY_PUBLIC_DOMAIN") or os.environ.get("RAILWAY_STATIC_URL")
    if domain:
        # Garante que tenha https:// e termine em /oauth/callback
        base = domain if domain.startswith("http") else f"https://{domain}"
        return f"{base.rstrip('/')}/oauth/callback"
    
    return "http://localhost:8000/oauth/callback"

REDIRECT_URI = get_redirect_uri()
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
    
    current_redirect = get_redirect_uri()
    url = (
        f"{RD_AUTH_URL}?response_type=code"
        f"&client_id={MKT_CLIENT_ID}"
        f"&redirect_uri={current_redirect}"
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
    except:
        client_id = 0

    current_redirect = get_redirect_uri()
    # RD Station exige Content-Type: application/x-www-form-urlencoded para o token exchange
    async with httpx.AsyncClient(timeout=20.0) as http:
        payload = {
            "client_id": MKT_CLIENT_ID,
            "client_secret": MKT_CLIENT_SECRET,
            "redirect_uri": current_redirect,
            "code": code,
            "grant_type": "authorization_code"
        }
        print(f"DEBUG OAuth: Trocando code por token para cliente {client_id}")
        print(f"DEBUG OAuth: Redirect URI usada: {current_redirect}")
        
        r = await http.post(RD_TOKEN_URL, data=payload)

    if r.status_code != 200:
        try:
            err_data = r.json()
            err_msg = err_data.get("error_description", err_data.get("error", f"HTTP {r.status_code}"))
        except:
            err_msg = f"HTTP {r.status_code}: {r.text[:100]}"
        return HTMLResponse(_error_html(f"Erro na troca do token: {err_msg}"))

    data = r.json()
    if "error" in data:
        return HTMLResponse(_error_html(f"Erro: {json.dumps(data)}"))

    access_token  = data.get("access_token", "")
    refresh_token = data.get("refresh_token", "")

    if client_id and access_token:
        try:
            print(f"DEBUG OAuth: Salvando token para cliente {client_id}")
            # Garante que o client_id seja tratado como int
            await save_mkt_token(int(client_id), access_token, refresh_token)
            print(f"DEBUG OAuth: Token salvo com sucesso!")
            
            # Verificação imediata pós-salvamento para diagnóstico
            from app.database import db_fetchone
            check = await db_fetchone("SELECT id, rd_token FROM clients WHERE id=$1", int(client_id))
            if check and check.get("rd_token"):
                print(f"DEBUG OAuth: Verificação de banco OK - Token presente para ID {client_id}")
            else:
                print(f"DEBUG OAuth: VERIFICAÇÃO DE BANCO FALHOU - Token não encontrado para ID {client_id} logo após salvamento")
        except Exception as e:
            import traceback
            err_stack = traceback.format_exc()
            print(f"DEBUG OAuth: ERRO ao salvar token: {e}")
            # Se falhar no banco, vamos tentar registrar o erro e avisar o usuário
            return HTMLResponse(_error_html(f"O RD Station autorizou, mas o banco de dados falhou ao salvar: {str(e)}<br><pre>{err_stack}</pre>"))
    else:
        print(f"DEBUG OAuth: Falha - client_id={client_id}, access_token={'presente' if access_token else 'ausente'}")
        return HTMLResponse(_error_html(f"Falha na identificação do cliente ou token vazio. Verifique se o ID do cliente ({client_id}) é válido."))

    return HTMLResponse(_success_html(client_id, "RD Marketing"))
