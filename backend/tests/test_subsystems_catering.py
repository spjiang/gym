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
    assert paid.json()["dining_status"] == "preparing"
    assert paid.json()["pickup_code"]

    cooking = client.get("/api/v1/catering/kitchen", headers=admin_headers, params={"merchant_id": bar["id"]})
    assert cooking.status_code == 200, cooking.text
    assert any(t["id"] == order["id"] and t["dining_status"] == "preparing" for t in cooking.json())

    too_early = client.post(
        f"/api/v1/catering/orders/{order['id']}/complete",
        headers=admin_headers,
    )
    assert too_early.status_code == 400

    ready = client.post(
        f"/api/v1/catering/orders/{order['id']}/ready",
        headers=admin_headers,
    )
    assert ready.status_code == 200, ready.text
    assert ready.json()["dining_status"] == "ready"

    board = client.get("/api/v1/catering/kitchen", headers=admin_headers, params={"merchant_id": bar["id"]})
    assert board.status_code == 200, board.text
    ticket = next((t for t in board.json() if t["id"] == order["id"]), None)
    assert ticket is not None
    assert ticket["dining_status"] == "ready"
    assert ticket["pickup_code"]
    assert ticket["items"]

    again = client.post(
        f"/api/v1/catering/orders/{order['id']}/ready",
        headers=admin_headers,
    )
    assert again.status_code == 400

    done = client.post(
        f"/api/v1/catering/orders/{order['id']}/complete",
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text
    assert done.json()["dining_status"] == "completed"

    gone = client.get("/api/v1/catering/kitchen", headers=admin_headers, params={"merchant_id": bar["id"]})
    assert gone.status_code == 200
    assert all(t["id"] != order["id"] for t in gone.json())

    refunded = client.post(f"/api/v1/orders/{order['id']}/refund", headers=admin_headers)
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"


def _png_bytes() -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )


def test_catering_menu_edit_and_image(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    bar = next((m for m in merchants if "catering" in (m.get("subsystem_codes") or [])), None)
    assert bar is not None
    created = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": bar["id"], "name": "可编辑小食", "category": "小食", "price": "18.00"},
    )
    assert created.status_code == 200, created.text
    item_id = created.json()["id"]

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    try:
        uploaded = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("dish.png", _png_bytes(), "image/png")},
        )
        assert uploaded.status_code == 200, uploaded.text
        url = uploaded.json()["url"]
        patched = client.patch(
            f"/api/v1/catering/menu-items/{item_id}",
            headers=admin_headers,
            json={
                "merchant_id": bar["id"],
                "name": "椒盐薯条",
                "category": "小食",
                "price": "26.00",
                "description": "现炸，撒椒盐",
                "image_url": url,
                "is_active": True,
            },
        )
        assert patched.status_code == 200, patched.text
        body = patched.json()
        assert body["name"] == "椒盐薯条"
        assert float(body["price"]) == 26
        assert body["image_url"] == url
        assert body["description"] == "现炸，撒椒盐"

        bad = client.patch(
            f"/api/v1/catering/menu-items/{item_id}",
            headers=admin_headers,
            json={
                "merchant_id": bar["id"],
                "name": "椒盐薯条",
                "category": "小食",
                "price": "26.00",
                "image_url": "https://example.com/a.jpg",
            },
        )
        assert bad.status_code == 400
    finally:
        get_settings.cache_clear()


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