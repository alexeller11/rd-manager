import os

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

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

app = FastAPI(title="RD Manager IA - Clean")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# =========================
# ROTAS PÚBLICAS
# =========================

app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(health.router, prefix="/api/health", tags=["health"])
app.include_router(oauth.router, prefix="/oauth", tags=["oauth"])


# =========================
# MÓDULOS NOVOS
# =========================

app.include_router(flows_advanced.router, prefix="/api/flows-adv", tags=["flows_advanced"])
app.include_router(landing_pages.router, prefix="/api/landing", tags=["landing_pages"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(insights.router, prefix="/api/insights", tags=["insights"])
app.include_router(prospect.router, prefix="/api/prospect", tags=["prospect"])


# =========================
# HEALTHCHECK
# =========================

@app.get("/health")
async def health_check():
    return {"status": "ok"}


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
