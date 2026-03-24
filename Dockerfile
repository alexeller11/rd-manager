FROM python:3.11-slim

WORKDIR /code

RUN pip install fastapi uvicorn

RUN printf '%s\n' \
'from fastapi import FastAPI' \
'app = FastAPI()' \
'@app.get("/health")' \
'async def health(): return {"ok": True}' \
> main.py

CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
