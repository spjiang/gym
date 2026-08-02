#!/usr/bin/env python3
"""端到端冒烟：底座路径 + 会籍办卡支付 → 通行 → 停卡拒行。"""

from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))

db_file = Path(tempfile.gettempdir()) / "gym_smoke.db"
if db_file.exists():
    db_file.unlink()

os.environ["DATABASE_URL"] = f"sqlite+pysqlite:///{db_file}"
os.environ["SECRET_KEY"] = "smoke-secret"
os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"
os.environ["SEED_ADMIN_USERNAME"] = "admin"
os.environ["SEED_ADMIN_PASSWORD"] = "Admin@123456"

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app import db as db_module
from app.config import get_settings
from app.db import Base, get_db
from app.main import create_app
from app.seed import run_seed

get_settings.cache_clear()
engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base.metadata.create_all(bind=engine)
db_module.engine = engine
db_module.SessionLocal = SessionLocal
run_seed()


def override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


app = create_app()
app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def main() -> None:
    assert client.get("/health").json()["status"] == "ok"
    token = client.post("/api/v1/auth/login", json={"username": "admin", "password": "Admin@123456"}).json()[
        "access_token"
    ]
    h = {"Authorization": f"Bearer {token}"}
    gym_id = client.get("/api/v1/merchants", headers=h).json()[0]["id"]

    member = client.post(
        "/api/v1/members",
        headers=h,
        json={"phone": "13800138000", "name": "冒烟会员", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=h,
        json={"name": "冒烟正门", "merchant_id": gym_id},
    ).json()
    client.post(
        "/api/v1/devices",
        headers=h,
        json={"access_point_id": point["id"], "device_code": "smoke-pad", "api_key": "smoke-key"},
    )

    product = client.post(
        "/api/v1/membership-products",
        headers=h,
        json={
            "merchant_id": gym_id,
            "name": "冒烟月卡",
            "product_type": "term",
            "price": "199.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text

    order = client.post(
        "/api/v1/memberships/purchase",
        headers=h,
        json={"member_id": member["id"], "product_id": product.json()["id"], "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=h,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200 and paid.json()["status"] == "paid", paid.text

    verify = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "smoke-pad", "X-Device-Key": "smoke-key"},
        json={"member_id": member["id"]},
    )
    assert verify.status_code == 200 and verify.json()["allowed"] is True, verify.text

    mid = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}", headers=h
    ).json()[0]["id"]
    freeze = client.post(f"/api/v1/memberships/{mid}/freeze", headers=h)
    assert freeze.status_code == 200, freeze.text
    denied = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "smoke-pad", "X-Device-Key": "smoke-key"},
        json={"member_id": member["id"]},
    )
    assert denied.json()["allowed"] is False, denied.text

    print("SMOKE OK: membership purchase / access allow / freeze deny")


if __name__ == "__main__":
    main()
