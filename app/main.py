import os

from fastapi import Depends, FastAPI  
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from app.utils.notifier import send_telegram_message

from app.auth_core import ensure_admin_exists, get_current_user, migrate_plaintext_rd_credentials
from app.core.settings import get_settings
from app.database import close_db, init_db
from app.routers import (
    agency_dashboard,
    agency_expert,
    alerts,
    auth,
    clients,
    executive_report,
    flows_advanced,
    health_audit,
    landing_pages,
    leads,
    oauth,
    prospect,
    rd_diagnostics,
    rd_fullsync,
    rd_modules,
    seo_geo,
)
from app.services.rd_fullsync import ensure_sync_tables

settings = get_settings()

app = FastAPI(
    title="RD Manager IA",
    version="1.0.0",
)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# CORS logic fix for wildcard + credentials
origins = settings.allowed_origins
allow_all = "*" in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if not allow_all else ["*"],
    allow_credentials=not allow_all, # credentials cannot be used with "*"
    allow_methods=["*"],
    allow_headers=["*"],
)

os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.on_event("startup")
async def startup() -> None:
    print("Tentando conectar ao banco de dados...")
    import os
    print (os.environ.get("DATABASE_URL"))
    await init_db()
    print("Conexão ao banco de dados estabelecida.")
    await ensure_admin_exists()
    await migrate_plaintext_rd_credentials()
    await ensure_sync_tables()


@app.on_event("shutdown")
async def shutdown() -> None:
    await close_db()


app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])

def _build_private_dependencies():
    return [Depends(get_current_user)]


private_dependencies = _build_private_dependencies()

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])

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
    rd_diagnostics.router,
    prefix="/api/rd-diagnostics",
    tags=["rd_diagnostics"],
    dependencies=private_dependencies,
)

app.include_router(
    rd_modules.router,
    prefix="/api/rd-modules",
    tags=["rd_modules"],
    dependencies=private_dependencies,
)

app.include_router(
    agency_dashboard.router,
    prefix="/api/agency",
    tags=["agency_dashboard"],
    dependencies=private_dependencies,
)

app.include_router(
    agency_expert.router,
    prefix="/api/agency-expert",
    tags=["agency_expert"],
    dependencies=private_dependencies,
)

app.include_router(
    seo_geo.router,
    prefix="/api/seo-geo",
    tags=["seo_geo"],
    dependencies=private_dependencies,
)

app.include_router(
    prospect.router,
    prefix="/api/prospect",
    tags=["prospect"],
    dependencies=private_dependencies,
)

app.include_router(
    executive_report.router,
    prefix="/api/executive-report",
    tags=["executive_report"],
    dependencies=private_dependencies,
)

app.include_router(
    leads.router,
    prefix="/api/leads",
    tags=["leads"],
    dependencies=private_dependencies,
)

app.include_router(
    landing_pages.router,
    prefix="/api/landing-pages",
    tags=["landing_pages"],
    dependencies=private_dependencies,
)

app.include_router(
    flows_advanced.router,
    prefix="/api/flows-advanced",
    tags=["flows_advanced"],
    dependencies=private_dependencies,
)

app.include_router(
    alerts.router,
    prefix="/api/alerts",
    tags=["alerts"],
    dependencies=private_dependencies,
)

app.include_router(
    health_audit.router,
    prefix="/api/health-audit",
    tags=["health_audit"],
    dependencies=private_dependencies,
)


@app.get("/health")
async def health_check():
    try:
        from app.database import engine
        async with engine.connect() as conn:
            await conn.run_sync(lambda sync_conn: sync_conn.execute(text("SELECT 1")))
        return {"status": "ok", "db": "connected"}
    except Exception as e:
        return {"status": "degraded", "error": str(e)}, 503
from sqlalchemy import text


@app.get("/", response_class=HTMLResponse)
async def root():
    path = os.path.join(BASE_DIR, "app", "templates", "index.html")

    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html não encontrado</h1>", status_code=500)

    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())
