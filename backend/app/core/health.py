"""依赖探查：Postgres 决定就绪，MinIO 仅降级。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from app.core import db as db_module


def _clip(err: BaseException) -> str:
    return str(err)[:200]


def check_postgres() -> dict[str, Any]:
    try:
        with db_module.engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True, "detail": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": _clip(exc)}


def check_minio() -> dict[str, Any]:
    try:
        from app.core.object_store import PUBLIC_BUCKET, minio_client

        minio_client().bucket_exists(PUBLIC_BUCKET)
        return {"ok": True, "detail": None}
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "detail": _clip(exc)}


def collect_readiness() -> dict[str, Any]:
    postgres = check_postgres()
    minio = check_minio()
    if not postgres["ok"]:
        status = "fail"
    elif not minio["ok"]:
        status = "degraded"
    else:
        status = "ok"
    return {
        "status": status,
        "postgres": postgres,
        "minio": minio,
        "checks": {
            "postgres": "ok" if postgres["ok"] else "fail",
            "minio": "ok" if minio["ok"] else "fail",
        },
    }
