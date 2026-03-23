FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

# O Railway injeta a variável PORT. Usamos 0.0.0.0 para aceitar conexões externas.
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]

# Healthcheck é gerenciado pelo railway.json ou plataforma de deploy
