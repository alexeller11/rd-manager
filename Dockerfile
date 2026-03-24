FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /code

COPY . /code

EXPOSE 8080

CMD ["sh", "-c", "python server.py"]
