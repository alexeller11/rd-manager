FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

RUN pip install --no-cache-dir fastapi==0.115.0 uvicorn[standard]==0.29.0

RUN printf '%s\n' \
'from fastapi import FastAPI' \
'app = FastAPI()' \
'@app.get("/health")' \
'async def health():' \
'    return {"status": "ok", "mode": "inline-fastapi"}' \
'@app.get("/")' \
'async def root():' \
'    return {"message": "inline fastapi running"}' \
> /code/main.py

EXPOSE 8080

CMD ["sh", "-c", "python -m uvicorn main:app --host 0.0.0.0 --port ${PORT:-8080} --log-level debug"]
