from fastapi import FastAPI

app = FastAPI(title="RD Manager IA - Minimal")

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "fastapi-minimal"}

@app.get("/")
async def root():
    return {"message": "fastapi minimal running"}
