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
    analysis,
    auth,
    campaign,
    clients,
    emails,
    flows,
    health,
    intelligence,
    oauth,
    rd_station,
    reports,
    scheduler,
    flows_advanced,
    landing_pages,
    leads,
    insights,
    prospect,
)

settings = get_settings()

app = FastAPI(title="RD Manager IA", version="5.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])

private_dependencies = [Depends(get_current_user)]

app.include_router(clients.router, prefix="/api/clients", tags=["clients"], dependencies=private_dependencies)
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"], dependencies=private_dependencies)
app.include_router(emails.router, prefix="/api/emails", tags=["emails"], dependencies=private_dependencies)
app.include_router(rd_station.router, prefix="/api/rd", tags=["rd_station"], dependencies=private_dependencies)
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=private_dependencies)
app.include_router(flows.router, prefix="/api/flows", tags=["flows"], dependencies=private_dependencies)
app.include_router(intelligence.router, prefix="/api/intel", tags=["intelligence"], dependencies=private_dependencies)
app.include_router(crm.router, prefix="/api/crm", tags=["crm"], dependencies=private_dependencies)
app.include_router(scheduler.router, prefix="/api/scheduler", tags=["scheduler"], dependencies=private_dependencies)
app.include_router(campaign.router, prefix="/api/campaign", tags=["campaign"], dependencies=private_dependencies)

if settings.debug_mode:
    from app.routers import debug
    app.include_router(
        debug.router,
        prefix="/api/debug",
        tags=["debug"],
        dependencies=[Depends(require_admin)],
    )

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "version": "5.0.0",
        "env": settings.app_env,
    }


@app.get("/", response_class=HTMLResponse)
async def root():
    path = os.path.join(BASE_DIR, "app", "templates", "index.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html não encontrado</h1>", status_code=500)
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/dashboard/{client_id}", response_class=HTMLResponse)
async def public_dashboard(client_id: int):
    path = os.path.join(BASE_DIR, "app", "templates", "public_dashboard.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>public_dashboard.html não encontrado</h1>", status_code=500)
    with open(path, "r", encoding="utf-8") as f:
        html = f.read().replace("{{CLIENT_ID}}", str(client_id))
    return HTMLResponse(html)
