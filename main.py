from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse

from app.database import init_db
from app.routers import clients
from app.routers import agency

app = FastAPI(title="RD Manager IA")

@app.on_event("startup")
async def startup():
    await init_db()

app.include_router(clients.router, prefix="/api/clients")
app.include_router(agency.router, prefix="/api/agency")

app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/")
async def root():
    return FileResponse("app/templates/index.html")

@app.get("/health")
async def health():
    return {"status": "ok"}
