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
