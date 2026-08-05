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

import app.models  # noqa: F401
from app.core import db as db_module
from app.core.config import get_settings
from app.core.db import Base, get_db
from app.main import create_app
from app.seed import run_seed

get_settings.cache_clear()


@pytest.fixture()
def client(tmp_path: Path):
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
