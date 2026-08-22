"""体检项回归：场地运营、退款权益、券占用、取餐号、厨房回退、停用桌台。"""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.systems.catering.api.member_catering import assign_pickup_code
from tests.test_agreements import enable_agreement


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _bar_id(client: TestClient, headers: dict) -> int:
    merchants = client.get("/api/v1/merchants", headers=headers).json()
    return next(m["id"] for m in merchants if "catering" in (m.get("subsystem_codes") or []))


def _member_headers(client: TestClient, phone: str) -> dict:
    from app.core.config import get_settings

    assert client.post("/api/v1/member/auth/otp/send", json={"phone": phone}).status_code == 200
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_pickup_code_unique_across_large_ids():
    assert assign_pickup_code(1) != assign_pickup_code(10001)
    assert assign_pickup_code(1).startswith("C")


def test_site_ops_can_list_members_and_orders(client: TestClient, admin_headers: dict):
    created = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "site_ops_qa",
            "password": "Ops@123456",
            "display_name": "场地运营",
            "merchant_id": None,
            "role_codes": ["site_ops"],
        },
    )
    assert created.status_code == 200, created.text
    assert created.json()["merchant_id"] is None

    token = client.post(
        "/api/v1/auth/login", json={"username": "site_ops_qa", "password": "Ops@123456"}
    ).json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    members = client.get("/api/v1/members", headers=headers)
    assert members.status_code == 200, members.text
    orders = client.get("/api/v1/orders", headers=headers)
    assert orders.status_code == 200, orders.text

    today = date.today().isoformat()
    report = client.get(
        f"/api/v1/reports/commerce-summary?date_from={today}&date_to={today}",
        headers=headers,
    )
    assert report.status_code == 200, report.text
    assert report.json()["merchant_id"] is None


def test_force_partial_membership_refund_keeps_card(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "部分退门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "部分退年卡",
            "product_type": "term",
            "price": "1000.00",
            "duration_days": 365,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13570000001", "name": "部分退会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    refunded = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "amount": "10.00", "reason": "force 部分退", "force": True},
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "paid"

    cards = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    )
    assert cards.status_code == 200, cards.text
    items = cards.json()["items"] if isinstance(cards.json(), dict) else cards.json()
    assert items
    assert items[0]["status"] != "void"


def test_coupon_cannot_bind_two_pending_orders(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    now = datetime.now(timezone.utc)
    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "占券",
            "discount_type": "fixed",
            "threshold_amount": "10.00",
            "fixed_amount": "5.00",
            "applicable_to": "retail",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=10)).isoformat(),
            "total_limit": 10,
        },
    )
    assert tpl.status_code == 200, tpl.text
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13570000002", "name": "占券会员", "merchant_id": gym_id},
    ).json()
    issued = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": tpl.json()["id"], "member_id": member["id"]},
    ).json()
    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={"merchant_id": gym_id, "name": "占券商品", "price": "20.00", "unit": "件", "low_stock_threshold": 1},
    ).json()
    client.post(f"/api/v1/retail/skus/{sku['id']}/stock/in", headers=admin_headers, json={"quantity": 10})

    first = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku["id"], "quantity": 1}],
            "member_coupon_id": issued["id"],
        },
    )
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku["id"], "quantity": 1}],
            "member_coupon_id": issued["id"],
        },
    )
    assert second.status_code == 400
    assert second.json()["code"] == "coupon_in_use"


def test_kitchen_undo_and_inactive_table_checkout(client: TestClient, admin_headers: dict):
    bar_id = _bar_id(client, admin_headers)
    item = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "回退测试饮品", "category": "饮品", "price": "18.00"},
    ).json()
    desk = client.post(
        "/api/v1/catering/tables",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "吧台位"},
    ).json()
    checkout = client.post(
        "/api/v1/catering/checkout",
        headers=admin_headers,
        json={
            "merchant_id": bar_id,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "table_no": desk["name"],
            "note": "不要冰",
        },
    )
    assert checkout.status_code == 200, checkout.text
    order_id = checkout.json()["id"]
    paid = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["pickup_code"]
    assert "吧台位" in (paid.json().get("customer_note") or "")

    ready = client.post(f"/api/v1/catering/orders/{order_id}/ready", headers=admin_headers)
    assert ready.status_code == 200
    undone = client.post(f"/api/v1/catering/orders/{order_id}/undo", headers=admin_headers)
    assert undone.status_code == 200, undone.text
    assert undone.json()["dining_status"] == "preparing"

    table = client.post(
        "/api/v1/catering/tables",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "停用桌Z"},
    ).json()
    deactivated = client.post(f"/api/v1/catering/tables/{table['id']}/deactivate", headers=admin_headers)
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13570000003", "name": "停用桌会员", "merchant_id": bar_id},
    ).json()
    mheaders = _member_headers(client, member["phone"])
    enable_agreement(client, admin_headers, bar_id, "dining", title="观野BAR点餐须知")
    blocked = client.post(
        "/api/v1/member/catering/checkout",
        headers=mheaders,
        json={
            "merchant_id": bar_id,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "table_no": "停用桌Z",
        },
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "table_inactive"


def test_pdf_requires_login_image_is_public(client: TestClient, admin_headers: dict, tmp_path, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path))
    get_settings.cache_clear()
    png = (
        b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
        b"\x08\x02\x00\x00\x00\x90wS\xde\x00\x00\x00\x0cIDATx\x9cc``\x00\x00"
        b"\x00\x04\x00\x01\xf6\x178U\x00\x00\x00\x00IEND\xaeB`\x82"
    )
    pdf = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n%%EOF\n"
    try:
        img = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("a.png", png, "image/png")},
        )
        assert img.status_code == 200, img.text
        assert client.get(img.json()["url"]).status_code == 200

        doc = client.post(
            "/api/v1/uploads",
            headers=admin_headers,
            files={"file": ("a.pdf", pdf, "application/pdf")},
        )
        assert doc.status_code == 200, doc.text
        url = doc.json()["url"]
        assert client.get(url).status_code == 401
        assert client.get(url, headers=admin_headers).status_code == 200
    finally:
        get_settings.cache_clear()
