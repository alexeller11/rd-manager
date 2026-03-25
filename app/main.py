import os

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.auth_core import (
    ensure_admin_exists,
    get_current_user,
    migrate_plaintext_rd_credentials,
    require_admin,
)
from app.core.settings import get_settings
from app.database import close_db, init_db
from app.routers import (
    auth,
    health,
    oauth,
    flows_advanced,
    landing_pages,
    leads,
    insights,
    prospect,
)

settings = get_settings()

app = FastAPI(title="RD Manager IA - Clean")
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# =========================
# STARTUP / SHUTDOWN
# =========================

@app.on_event("startup")
async def startup() -> None:
    print("🚀 Iniciando RD Manager IA...")
    print(f"🌍 Ambiente: {settings.app_env}")
    print(f"🐞 Debug: {settings.debug_mode}")

    await init_db()
    await ensure_admin_exists()
    await migrate_plaintext_rd_credentials()

    print("✅ Aplicação pronta.")


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()
    print("🛑 Aplicação encerrada com conexão de banco fechada.")


# =========================
# ROTAS PÚBLICAS
# =========================

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])


# =========================
# ROTAS PRIVADAS
# =========================

private_dependencies = [Depends(get_current_user)]

app.include_router(
    flows_advanced.router,
    prefix="/api/flows-adv",
    tags=["flows_advanced"],
    dependencies=private_dependencies,
)

app.include_router(
    landing_pages.router,
    prefix="/api/landing",
    tags=["landing_pages"],
    dependencies=private_dependencies,
)

app.include_router(
    leads.router,
    prefix="/api/leads",
    tags=["leads"],
    dependencies=private_dependencies,
)

app.include_router(
    insights.router,
    prefix="/api/insights",
    tags=["insights"],
    dependencies=private_dependencies,
)

app.include_router(
    prospect.router,
    prefix="/api/prospect",
    tags=["prospect"],
    dependencies=private_dependencies,
)


# =========================
# DEBUG
# =========================

if settings.debug_mode:
    from app.routers import debug

    app.include_router(
        debug.router,
        prefix="/api/debug",
        tags=["debug"],
        dependencies=[Depends(require_admin)],
    )


# =========================
# HEALTHCHECK
# =========================

@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "env": settings.app_env,
        "version": "6.1.0",
    }


# =========================
# FRONTEND
# =========================

@app.get("/", response_class=HTMLResponse)
async def root():
    path = os.path.join(BASE_DIR, "app", "templates", "index.html")

    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html não encontrado</h1>", status_code=500)

    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


# =========================
# TESTE
# =========================

@app.get("/test")
async def test():
    return {"msg": "esse é o main NOVO"}
