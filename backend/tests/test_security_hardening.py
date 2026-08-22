"""支付、推广、提现、提成安全回归。"""

from decimal import Decimal

from fastapi.testclient import TestClient

from app.systems.platform.models.commerce import PaymentChannel


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _other_gym_id(client: TestClient, headers: dict, gym_id: int) -> int:
    merchants = client.get("/api/v1/merchants", headers=headers).json()
    for m in merchants:
        if m["id"] != gym_id and "gym" in (m.get("subsystem_codes") or []):
            return m["id"]
    types = client.get("/api/v1/merchant-types", headers=headers).json()
    gym_type = next(t for t in types if t["code"] == "gym")
    created = client.post(
        "/api/v1/merchants",
        headers=headers,
        json={"merchant_type_id": gym_type["id"], "name": "安全测他店", "status": "active"},
    )
    assert created.status_code == 200, created.text
    return created.json()["id"]


def _merchant_admin_headers(client: TestClient, admin_headers: dict, gym_id: int) -> dict:
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "sec_gym_admin",
            "password": "Sec@123456",
            "display_name": "安全商管",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "sec_gym_admin", "password": "Sec@123456"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _site_finance_headers(client: TestClient, admin_headers: dict) -> dict:
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "sec_finance",
            "password": "Sec@123456",
            "display_name": "安全财务",
            "merchant_id": None,
            "role_codes": ["site_finance"],
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "sec_finance", "password": "Sec@123456"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pay_query_blocks_cross_merchant(client: TestClient, admin_headers: dict):
    gym_a = _gym_id(client, admin_headers)
    gym_b = _other_gym_id(client, admin_headers, gym_a)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_b,
            "title": "跨店查单测",
            "amount": "10.00",
            "order_type": "retail",
        },
    ).json()
    mheaders = _merchant_admin_headers(client, admin_headers, gym_a)
    resp = client.post(f"/api/v1/orders/{order['id']}/pay/query", headers=mheaders)
    assert resp.status_code == 403


def test_mark_offline_refunded_rejects_processing_wechat(
    client: TestClient, admin_headers: dict
):
    gym_id = _gym_id(client, admin_headers)
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "title": "对账退测",
            "amount": "50.00",
            "order_type": "retail",
        },
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    from app.core.db import SessionLocal
    from app.systems.platform.models.payment_settings import RefundIntent

    db = SessionLocal()
    try:
        intent = RefundIntent(
            site_id=1,
            order_id=order["id"],
            out_refund_no=f"sec-{order['id']}",
            out_trade_no=f"o{order['id']}",
            amount=Decimal("10.00"),
            suggested_amount=Decimal("50.00"),
            channel=PaymentChannel.WECHAT_ORIGINAL.value,
            status="processing",
        )
        db.add(intent)
        db.commit()
        db.refresh(intent)
        intent_id = intent.id
    finally:
        db.close()

    fheaders = _site_finance_headers(client, admin_headers)
    resp = client.post(
        "/api/v1/site/payment-reconcile/actions/mark-offline-refunded",
        headers=fheaders,
        json={"refund_intent_id": intent_id, "reason": "误点"},
    )
    assert resp.status_code == 400


def test_site_finance_can_list_all_payouts(client: TestClient, admin_headers: dict):
    fheaders = _site_finance_headers(client, admin_headers)
    resp = client.get("/api/v1/payouts", headers=fheaders)
    assert resp.status_code == 200, resp.text


def test_commission_read_cannot_request_my_payout(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "sec_gym_ops",
            "password": "Sec@123456",
            "display_name": "安全运营",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    )
    token = client.post(
        "/api/v1/auth/login",
        json={"username": "sec_gym_ops", "password": "Sec@123456"},
    ).json()["access_token"]
    resp = client.post("/api/v1/my/payouts", headers={"Authorization": f"Bearer {token}"}, json={})
    assert resp.status_code == 403
