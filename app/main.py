import os
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.routers import auth, clients, analysis, emails, rd_station, reports
from app.routers import health, flows, intelligence, crm, oauth, scheduler, campaign

app = FastAPI(title="RD Manager IA", version="4.0.0")

# ─── CORS ─────────────────────────────────────────────────────────────────────
# allow_origins=["*"] + allow_credentials=True é inválido pelo spec do CORS.
# Escolhemos uma das duas abordagens:
ALLOWED_ORIGINS = os.environ.get(
    "ALLOWED_ORIGINS",
    os.environ.get("RAILWAY_STATIC_URL", "https://alexeller-rd-manager.hf.space") + ",http://localhost:3000,http://localhost:8000"
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Routers ──────────────────────────────────────────────────────────────────
app.include_router(auth.router,        prefix="/api/auth",      tags=["auth"])
app.include_router(clients.router,     prefix="/api/clients",   tags=["clients"])
app.include_router(analysis.router,    prefix="/api/analysis",  tags=["analysis"])
app.include_router(emails.router,      prefix="/api/emails",    tags=["emails"])
app.include_router(rd_station.router,  prefix="/api/rd",        tags=["rd_station"])
app.include_router(reports.router,     prefix="/api/reports",   tags=["reports"])
app.include_router(health.router,      prefix="/api/health",    tags=["health"])
app.include_router(flows.router,       prefix="/api/flows",     tags=["flows"])
app.include_router(intelligence.router,prefix="/api/intel",     tags=["intelligence"])
app.include_router(crm.router,         prefix="/api/crm",       tags=["crm"])
app.include_router(scheduler.router,   prefix="/api/scheduler", tags=["scheduler"])
app.include_router(campaign.router,    prefix="/api/campaign",  tags=["campaign"])
app.include_router(oauth.router,       prefix="/oauth",         tags=["oauth"])

# Debug router: apenas se DEBUG_MODE=true
if os.environ.get("DEBUG_MODE", "").lower() == "true":
    from app.routers import debug
    app.include_router(debug.router, prefix="/api/debug", tags=["debug"])

# ─── Static files ─────────────────────────────────────────────────────────────
os.makedirs("app/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


# ─── Startup ──────────────────────────────────────────────────────────────────
@app.on_event("startup")
async def startup():
    await init_db()


# ─── Rotas HTML ───────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def root():
    with open("app/templates/index.html", "r") as f:
        return HTMLResponse(content=f.read())


@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "4.0.0"}


@app.get("/dashboard/{client_id}", response_class=HTMLResponse)
async def public_dashboard(client_id: int):
    with open("app/templates/public_dashboard.html", "r") as f:
        html = f.read().replace("{{CLIENT_ID}}", str(client_id))
    return HTMLResponse(content=html)
