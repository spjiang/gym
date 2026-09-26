"""支付退款加固契约测试。"""

from decimal import Decimal

from fastapi.testclient import TestClient


def test_plaintext_notify_rejected_when_not_dry_run(client: TestClient, admin_headers: dict):
    client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={
            "mode": "wechat",
            "dry_run": False,
            "mp_app_id": "wx_app",
            "mch_id": "mch1",
            "api_v3_key": "k" * 32,
        },
    )
    # 无密文明文回调必须失败（即使有虚构 out_trade_no）
    resp = client.post("/api/v1/payments/wechat/notify", json={"out_trade_no": "no-such"})
    assert resp.status_code == 200
    assert resp.json()["code"] == "FAIL"


def test_refund_preview_and_offline_full_refund(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "退款测", "amount": "50.00"},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    preview = client.get(f"/api/v1/orders/{order['id']}/refund/preview", headers=admin_headers)
    assert preview.status_code == 200, preview.text
    assert preview.json()["suggested_amount"] == "50.00"

    refunded = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "顾客取消", "amount": "50.00"},
    )
    assert refunded.status_code == 200, refunded.text
    body = refunded.json()
    assert body["status"] == "refunded"
    assert Decimal(body.get("refunded_amount") or "0") == Decimal("50.00")


def test_partial_retail_refund_keeps_paid(client: TestClient, admin_headers: dict):
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym_id, "order_type": "retail", "title": "部分退", "amount": "100.00"},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_transfer"},
    )
    partial = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_transfer", "amount": "30.00", "reason": "部分退"},
    )
    assert partial.status_code == 200, partial.text
    assert partial.json()["status"] == "paid"
    assert Decimal(partial.json()["refunded_amount"]) == Decimal("30.00")


def test_reconcile_list_requires_permission(client: TestClient, admin_headers: dict):
    resp = client.get("/api/v1/site/payment-reconcile/items?kind=pay_stale", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    assert "items" in resp.json()


def test_refund_notify_voids_membership_without_staff(client: TestClient, admin_headers: dict):
    """微信退款回调没有员工身份，作废会籍不能写入不存在的员工 0。"""
    from decimal import Decimal as D

    from app.core.db import SessionLocal
    from app.systems.platform.models.payment_settings import RefundIntent
    from app.systems.platform.services.refunds import apply_refund_success

    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000981", "name": "退款回调", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "退款门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "体验卡回调",
            "product_type": "term",
            "duration_days": 1,
            "price": "0.01",
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    purchase = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "product_id": product.json()["id"],
        },
    )
    assert purchase.status_code == 200, purchase.text
    order = purchase.json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    db = SessionLocal()
    try:
        intent = RefundIntent(
            site_id=order["site_id"],
            order_id=order["id"],
            out_refund_no=f"r-notify-{order['id']}",
            out_trade_no=f"o-notify-{order['id']}",
            amount=D(order["amount"]),
            suggested_amount=D(order["amount"]),
            channel="wechat_original",
            status="processing",
            force=False,
            reason="管理端退款",
        )
        db.add(intent)
        db.flush()
        apply_refund_success(db, intent, actor_staff_id=None)
        db.commit()
        assert intent.status == "succeeded"
    finally:
        db.close()

    detail = client.get(f"/api/v1/orders/{order['id']}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["status"] == "refunded"
    listed = client.get("/api/v1/orders/refunds", headers=admin_headers)
    assert listed.status_code == 200, listed.text
    hit = next(item for item in listed.json()["items"] if item["order_id"] == order["id"])
    refund_detail = client.get(f"/api/v1/orders/refunds/{hit['id']}", headers=admin_headers)
    assert refund_detail.status_code == 200, refund_detail.text
    body = refund_detail.json()
    assert body["status"] == "succeeded"
    assert body["order"]["id"] == order["id"]
    assert body["order"]["buyer"]["phone"] == "13900000981"
    assert body["order"]["store"]["id"] == gym_id
