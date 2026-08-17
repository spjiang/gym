FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl \
  && rm -rf /var/lib/apt/lists/*

# 先装依赖，源码变化才不会打掉 pip 缓存层
COPY requirements.txt ./
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -U pip && pip install -r requirements.txt

COPY alembic.ini ./
COPY alembic ./alembic
COPY scripts ./scripts
COPY app ./app

EXPOSE 8000

CMD ["bash", "scripts/entrypoint.sh"]
