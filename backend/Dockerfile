FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
COPY app ./app
COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts

RUN pip install --no-cache-dir -U pip \
  && pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

CMD ["bash", "scripts/entrypoint.sh"]