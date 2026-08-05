"""活动价、微信支付配置与 OTP 通道测试。"""

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_promo_price_on_membership_purchase(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13660000001", "name": "活动价客", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "活动门", "merchant_id": gym_id},
    ).json()
    now = datetime.now(timezone.utc)
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "活动月卡",
            "product_type": "term",
            "price": "299.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
            "promo_price": "199.00",
            "promo_starts_at": (now - timedelta(hours=1)).isoformat(),
            "promo_ends_at": (now + timedelta(days=3)).isoformat(),
        },
    )
    assert product.status_code == 200, product.text
    assert product.json()["effective_price"] == "199.00"

    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product.json()["id"], "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    assert order.json()["amount"] == "199.00"


def test_wechat_mode_requires_credentials(client: TestClient, admin_headers: dict, monkeypatch):
    monkeypatch.setenv("ONLINE_PAYMENT_MODE", "wechat")
    monkeypatch.setenv("WECHAT_APP_ID", "")
    monkeypatch.setenv("WECHAT_MCH_ID", "")
    monkeypatch.setenv("WECHAT_API_KEY", "")
    get_settings.cache_clear()
    gym_id = _gym_id(client, admin_headers)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "微信测", "amount": "1.00"},
    ).json()
    pay = client.post(f"/api/v1/orders/{order['id']}/pay/online", headers=admin_headers, json={})
    assert pay.status_code == 503
    get_settings.cache_clear()
    os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"


def test_wechat_dry_run_success(client: TestClient, admin_headers: dict, monkeypatch):
    monkeypatch.setenv("ONLINE_PAYMENT_MODE", "wechat")
    monkeypatch.setenv("WECHAT_APP_ID", "wx_test")
    monkeypatch.setenv("WECHAT_MCH_ID", "mch_test")
    monkeypatch.setenv("WECHAT_API_KEY", "key_test")
    monkeypatch.setenv("WECHAT_DRY_RUN", "true")
    get_settings.cache_clear()
    gym_id = _gym_id(client, admin_headers)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "微信干跑", "amount": "2.00"},
    ).json()
    pay = client.post(f"/api/v1/orders/{order['id']}/pay/online", headers=admin_headers, json={})
    assert pay.status_code == 200, pay.text
    assert pay.json()["status"] == "paid"
    get_settings.cache_clear()
    os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"
