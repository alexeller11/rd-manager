import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.auth_core import (
    ensure_admin_exists,
    get_current_user,
    migrate_plaintext_rd_credentials,
)
from app.core.settings import get_settings
from app.database import close_db, init_db
from app.routers import (
    agency_dashboard,
    auth,
    clients,
    oauth,
    rd_fullsync,
)

print("🔥 ESTE É O MAIN CORRETO 🔥")

settings = get_settings()

app = FastAPI(
    title="RD Manager IA",
    version="12.0.1",
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=getattr(settings, "allowed_origins", ["*"]),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.on_event("startup")
async def startup() -> None:
    print("🚀 Iniciando RD Manager IA...")
    print(f"🌍 Ambiente: {getattr(settings, 'app_env', 'production')}")
    print(f"🐞 Debug: {getattr(settings, 'debug_mode', False)}")

    await init_db()
    await ensure_admin_exists()
    await migrate_plaintext_rd_credentials()

    print("✅ Aplicação pronta.")


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()
    print("🛑 Aplicação encerrada com conexão de banco fechada.")


# rotas públicas
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])


# rotas privadas
private_dependencies = [Depends(get_current_user)]

app.include_router(
    clients.router,
    prefix="/api/clients",
    tags=["clients"],
    dependencies=private_dependencies,
)

app.include_router(
    rd_fullsync.router,
    prefix="/api/rdsync",
    tags=["rd_fullsync"],
    dependencies=private_dependencies,
)

app.include_router(
    agency_dashboard.router,
    prefix="/api/agency",
    tags=["agency_dashboard"],
    dependencies=private_dependencies,
)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "env": getattr(settings, "app_env", "production"),
        "version": "12.0.1",
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    path = os.path.join(BASE_DIR, "app", "templates", "index.html")

    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html não encontrado</h1>", status_code=500)

    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
