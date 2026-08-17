#!/usr/bin/env bash
set -euo pipefail

echo "[entrypoint] 等待数据库并执行迁移..."
python - <<'PY'
import os, time
from sqlalchemy import create_engine, text

url = os.environ["DATABASE_URL"]
engine = create_engine(url, pool_pre_ping=True)
for i in range(60):
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("[entrypoint] 数据库就绪")
        break
    except Exception as exc:
        print(f"[entrypoint] 等待数据库 ({i+1}/60): {exc}")
        time.sleep(2)
else:
    raise SystemExit("数据库长时间未就绪")
PY

alembic upgrade head
python -m app.seed

reload_args=()
if [ "${UVICORN_RELOAD:-}" = "1" ]; then
  reload_args+=(--reload)
fi
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 "${reload_args[@]}"