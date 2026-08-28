"""测试夹具：临时 SQLite 文件 + TestClient。"""

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker

# 在导入 app 前设置测试环境
os.environ["DATABASE_URL"] = "sqlite+pysqlite:///:memory:"
os.environ["SECRET_KEY"] = "test-secret"
os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"
os.environ["SEED_ADMIN_USERNAME"] = "admin"
os.environ["SEED_ADMIN_PASSWORD"] = "Admin@123456"
os.environ["SEED_DEMO"] = "false"
os.environ["MINIO_ENDPOINT"] = "127.0.0.1:8900"
os.environ["MINIO_ACCESS_KEY"] = "gymminio"
os.environ["MINIO_SECRET_KEY"] = "change-me-minio-secret"
os.environ["MINIO_USE_SSL"] = "false"
os.environ["FILE_PUBLIC_BASE_URL"] = "http://localhost:8900/public"


def _require_minio() -> None:
    import socket

    try:
        with socket.create_connection(("127.0.0.1", 8900), timeout=2):
            return
    except OSError as exc:
        raise RuntimeError(
            "pytest 需要本机 MinIO：在仓库根目录执行 docker compose up -d minio"
        ) from exc


_require_minio()

import httpx

import app.models  # noqa: F401
from app.core import db as db_module
from app.core.config import get_settings
from app.core.db import Base, get_db
from app.main import create_app
from app.seed import run_seed

get_settings.cache_clear()


def fetch_public_url(url: str):
    """读公开桶对象，不走系统代理（本机 Clash 等会把 localhost:8900 打成 502）。"""
    return httpx.get(url, timeout=5, trust_env=False)


@pytest.fixture()
def client(tmp_path: Path):
    get_settings.cache_clear()
    os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"
    os.environ["WECHAT_DRY_RUN"] = "true"
    get_settings.cache_clear()
    db_path = tmp_path / "test.db"
    url = f"sqlite+pysqlite:///{db_path}"
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()

    engine = create_engine(url, connect_args={"check_same_thread": False})
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    Base.metadata.create_all(bind=engine)
    assert "sites" in inspect(engine).get_table_names(), "建表失败"

    db_module.engine = engine
    db_module.SessionLocal = TestingSessionLocal

    run_seed()

    def _override_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app = create_app()
    app.dependency_overrides[get_db] = _override_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    engine.dispose()
    get_settings.cache_clear()


@pytest.fixture()
def admin_headers(client: TestClient) -> dict[str, str]:
    resp = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123456"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


_coach_member_seq = {"n": 0}


def new_coach_member(client: TestClient, headers: dict, gym_id: int, name: str = "教练会员") -> dict:
    """创建供教练绑定的会员主档。"""
    _coach_member_seq["n"] += 1
    phone = f"1398{str(_coach_member_seq['n']).zfill(7)}"[:11]
    resp = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": phone, "name": name, "merchant_id": gym_id},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()
