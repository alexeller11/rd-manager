import logging
import os
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

# Importações do núcleo do seu sistema
from app.auth_core import ensure_admin_exists, get_current_user, migrate_plaintext_rd_credentials
from app.core.settings import get_settings
from app.database import close_db, init_db, db_fetchval, db_execute, using_postgres
from app.routers import (
    agency_dashboard,
    agency_expert,
    alerts,
    analysis,
    auth,
    campaign,
    clients,
    crm,
    emails,
    executive_report,
    flows_advanced,
    health_audit,
    intelligence,
    landing_pages,
    leads,
    oauth,
    prospect,
    rd_aggregator,
    rd_diagnostics,
    rd_fullsync,
    rd_modules,
    reports,
    seo_geo,
    webhooks,
)
from app.services.rd_fullsync import ensure_sync_tables
from app.routers.rd_station import close_http_client

logger = logging.getLogger(__name__)
settings = get_settings()

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Gerencia o ciclo de vida do App. 
    O startup garante que o banco e as tabelas existam.
    """
    # ── Startup ───────────────────────────────────────────────────────────────────
    # init_db() chama init_schema() internamente, criando as tabelas se não existirem
    await init_db() 
    
    await ensure_admin_exists()
    await migrate_plaintext_rd_credentials()
    await ensure_sync_tables()
    
    logger.info("✅ RD Manager IA: Banco de dados pronto e tabelas verificadas.")
    yield
    
    # ── Shutdown ───────────────────────────────────────────────────────────────
    await close_db()
    await close_http_client()
    logger.info("🛑 RD Manager IA: Encerrado com sucesso.")


app = FastAPI(
    title="RD Manager IA",
    version="4.1.0",
    lifespan=lifespan,
)

# Configuração de CORS (Segurança para o Frontend)
origins = settings.allowed_origins
allow_all = "*" in origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins if not allow_all else ["*"],
    allow_credentials=not allow_all,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Servir arquivos estáticos (CSS, JS, Imagens)
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ── Rotas Públicas (Abertas) ──────────────────────────────────────────────────
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])
app.include_router(webhooks.router, tags=["webhooks"])


# Dependência de Autenticação para rotas privadas
def _build_private_dependencies():
    return [Depends(get_current_user)]

private_dependencies = _build_private_dependencies()

# ── Registro de todos os Módulos do Sistema ──────────────────────────────────
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(clients.router, prefix="/api/clients", tags=["clients"], dependencies=private_dependencies)
app.include_router(rd_fullsync.router, prefix="/api/rdsync", tags=["rd_fullsync"], dependencies=private_dependencies)
app.include_router(rd_diagnostics.router, prefix="/api/rd-diagnostics", tags=["rd_diagnostics"], dependencies=private_dependencies)
app.include_router(rd_modules.router, prefix="/api/rd-modules", tags=["rd_modules"], dependencies=private_dependencies)
app.include_router(rd_aggregator.router, prefix="/api/rd-aggregator", tags=["rd_aggregator"], dependencies=private_dependencies)
app.include_router(agency_dashboard.router, prefix="/api/agency", tags=["agency_dashboard"], dependencies=private_dependencies)
app.include_router(agency_expert.router, prefix="/api/agency-expert", tags=["agency_expert"], dependencies=private_dependencies)
app.include_router(analysis.router, prefix="/api/analysis", tags=["analysis"], dependencies=private_dependencies)
app.include_router(intelligence.router, prefix="/api/intelligence", tags=["intelligence"], dependencies=private_dependencies)
app.include_router(reports.router, prefix="/api/reports", tags=["reports"], dependencies=private_dependencies)
app.include_router(executive_report.router, prefix="/api/executive-report", tags=["executive_report"], dependencies=private_dependencies)
app.include_router(leads.router, prefix="/api/leads", tags=["leads"], dependencies=private_dependencies)
app.include_router(crm.router, prefix="/api/crm", tags=["crm"], dependencies=private_dependencies)
app.include_router(campaign.router, prefix="/api/campaigns", tags=["campaigns"], dependencies=private_dependencies)
app.include_router(emails.router, prefix="/api/emails", tags=["emails"], dependencies=private_dependencies)
app.include_router(landing_pages.router, prefix="/api/landing-pages", tags=["landing_pages"], dependencies=private_dependencies)
app.include_router(flows_advanced.router, prefix="/api/flows-advanced", tags=["flows_advanced"], dependencies=private_dependencies)
app.include_router(alerts.router, prefix="/api/alerts", tags=["alerts"], dependencies=private_dependencies)
app.include_router(health_audit.router, prefix="/api/health-audit", tags=["health_audit"], dependencies=private_dependencies)
app.include_router(seo_geo.router, prefix="/api/seo-geo", tags=["seo_geo"], dependencies=private_dependencies)
app.include_router(prospect.router, prefix="/api/prospect", tags=["prospect"], dependencies=private_dependencies)


@app.get("/health")
async def health_check():
    """Rota de verificação de saúde para o Render"""
    try:
        await db_fetchval("SELECT 1")
        return {"status": "ok", "version": "4.1.0", "db": "connected"}
    except Exception as e:
        return JSONResponse(
            content={"status": "degraded", "error": str(e)},
            status_code=503,
        )


@app.get("/", response_class=HTMLResponse)
async def root():
    """Carrega o Frontend React"""
    path = os.path.join(BASE_DIR, "app", "templates", "index.html")
    if not os.path.exists(path):
        return HTMLResponse("<h1>index.html não encontrado</h1>", status_code=500)
    with open(path, "r", encoding="utf-8") as f:
        return HTMLResponse(f.read())