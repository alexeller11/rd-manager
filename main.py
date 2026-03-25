from fastapi import FastAPI

app = FastAPI(title="RD Manager IA - Minimal")

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "fastapi-minimal"}

@app.get("/")
async def root():
    return {"message": "fastapi minimal running"}
from app.routers import flows_advanced, landing_pages, leads, insights, prospect

app.include_router(flows_advanced.router, prefix="/api/flows-adv")
app.include_router(landing_pages.router, prefix="/api/landing")
app.include_router(leads.router, prefix="/api/leads")
app.include_router(insights.router, prefix="/api/insights")
app.include_router(prospect.router, prefix="/api/prospect")
