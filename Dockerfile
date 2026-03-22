FROM python:3.11-slim

WORKDIR /code

COPY ./requirements.txt /code/requirements.txt
RUN pip install --no-cache-dir --upgrade -r /code/requirements.txt

COPY . /code

# Railway fornece a variável PORT automaticamente
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
