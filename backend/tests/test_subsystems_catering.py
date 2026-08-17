"""商户业态子系统与餐饮点单闭环。"""

from fastapi.testclient import TestClient


def test_merchant_subsystems_and_order_type_filter(client: TestClient, admin_headers: dict):
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar = next(t for t in types if t["code"] == "bar")
    created = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar["id"],
            "name": "测试清吧A",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    )
    assert created.status_code == 200, created.text
    mid = created.json()["id"]
    assert created.json()["subsystem_codes"] == ["catering"]

    types_allowed = client.get(f"/api/v1/merchants/{mid}/order-types", headers=admin_headers)
    assert types_allowed.status_code == 200
    values = {x["value"] for x in types_allowed.json()}
    assert "dining" in values
    assert "retail" in values
    assert "membership" not in values

    bad = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": mid, "title": "办月卡", "amount": "299", "order_type": "membership"},
    )
    assert bad.status_code == 400

    ok = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": mid, "title": "吧台现结", "amount": "68", "order_type": "dining"},
    )
    assert ok.status_code == 200, ok.text


def test_catering_checkout_pay_refund_loop(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    bar = next((m for m in merchants if "catering" in (m.get("subsystem_codes") or [])), None)
    assert bar is not None, "种子应包含餐饮商户"

    menu = client.get(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        params={"merchant_id": bar["id"], "active_only": True},
    )
    assert menu.status_code == 200, menu.text
    items = menu.json()["items"]
    if not items:
        created_item = client.post(
            "/api/v1/catering/menu-items",
            headers=admin_headers,
            json={
                "merchant_id": bar["id"],
                "name": "测试啤酒",
                "category": "酒水",
                "price": "30.00",
            },
        )
        assert created_item.status_code == 200, created_item.text
        items = [created_item.json()]

    checkout = client.post(
        "/api/v1/catering/checkout",
        headers=admin_headers,
        json={
            "merchant_id": bar["id"],
            "items": [{"menu_item_id": items[0]["id"], "quantity": 2}],
        },
    )
    assert checkout.status_code == 200, checkout.text
    order = checkout.json()
    assert order["order_type"] == "dining"
    assert order["status"] == "pending"
    assert float(order["amount"]) > 0

    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    refunded = client.post(f"/api/v1/orders/{order['id']}/refund", headers=admin_headers)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"


def test_gym_merchant_rejects_dining(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym = next((m for m in merchants if "gym" in (m.get("subsystem_codes") or [])), None)
    assert gym is not None
    r = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={"merchant_id": gym["id"], "title": "清吧单", "amount": "10", "order_type": "dining"},
    )
    assert r.status_code == 400


def test_bar_rejects_membership_product(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    bar = next((m for m in merchants if "catering" in (m.get("subsystem_codes") or [])), None)
    assert bar is not None
    r = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": bar["id"],
            "name": "清吧不应有月卡",
            "product_type": "term",
            "price": "100",
            "duration_days": 30,
            "access_point_ids": [],
            "is_active": False,
        },
    )
    assert r.status_code == 403
    assert r.json()["code"] == "subsystem_not_linked"