from fastapi import FastAPI

app = FastAPI(title="RD Manager IA", version="5.0.0-diagnostic")


@app.get("/health")
async def health():
    return {"status": "ok", "mode": "diagnostic"}


@app.get("/")
async def root():
    return {"status": "ok", "message": "RD Manager diagnostic boot successful"}
