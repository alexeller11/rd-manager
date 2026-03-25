from fastapi import FastAPI

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


# Rotas públicas
app.include_router(auth.router, prefix="/api/auth")
app.include_router(health.router, prefix="/api/health")
app.include_router(oauth.router, prefix="/oauth")

# Módulos novos
app.include_router(flows_advanced.router, prefix="/api/flows-adv")
app.include_router(landing_pages.router, prefix="/api/landing")
app.include_router(leads.router, prefix="/api/leads")
app.include_router(insights.router, prefix="/api/insights")
app.include_router(prospect.router, prefix="/api/prospect")


@app.get("/health")
async def health_check():
    return {"status": "ok"}


@app.get("/")
async def root():
    return {"message": "RD Manager IA clean running"}
