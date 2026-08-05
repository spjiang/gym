"""会员端餐饮闭环测试。"""

import os

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _member_login(client: TestClient, phone: str) -> dict:
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    code = get_settings().member_otp_mock_code
    verify = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_member_me_includes_merchants(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar_type = next(t for t in types if t["code"] == "bar")
    bar = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar_type["id"],
            "name": "测试清吧H5",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000091", "name": "双店会员", "merchant_id": gym_id},
    ).json()
    link = client.post(
        f"/api/v1/members/{member['id']}/merchants",
        headers=admin_headers,
        json={"merchant_id": bar["id"]},
    )
    assert link.status_code == 200, link.text

    mheaders = _member_login(client, "13880000091")
    me = client.get("/api/v1/member/me", headers=mheaders).json()
    assert "merchants" in me
    ids = {m["id"] for m in me["merchants"]}
    assert gym_id in ids and bar["id"] in ids


def test_member_dining_checkout_pay_refund(client: TestClient, admin_headers: dict):
    os.environ["ONLINE_PAYMENT_MODE"] = "mock"
    get_settings.cache_clear()

    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar_type = next(t for t in types if t["code"] == "bar")
    bar = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar_type["id"],
            "name": "点餐测试清吧",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()
    bar_id = bar["id"]

    # 用超管/清吧权限建菜单：先建 bar_admin 员工或用超管调 catering API
    item = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={
            "merchant_id": bar_id,
            "name": "特调气泡水",
            "category": "饮品",
            "price": "28.00",
            "is_active": True,
        },
    )
    assert item.status_code == 200, item.text
    item_id = item.json()["id"]

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000092", "name": "点餐客", "merchant_id": bar_id},
    ).json()
    mheaders = _member_login(client, member["phone"])

    menu = client.get(
        "/api/v1/member/catering/menu",
        params={"merchant_id": bar_id},
        headers=mheaders,
    )
    assert menu.status_code == 200, menu.text
    assert any(x["id"] == item_id for x in menu.json())

    order = client.post(
        "/api/v1/member/catering/checkout",
        headers=mheaders,
        json={
            "merchant_id": bar_id,
            "items": [{"menu_item_id": item_id, "quantity": 2}],
            "note": "少冰",
            "table_no": "A3",
        },
    )
    assert order.status_code == 200, order.text
    order_body = order.json()
    assert order_body["status"] == "pending"
    assert order_body["order_type"] == "dining"
    assert "桌号:A3" in (order_body.get("customer_note") or "")

    paid = client.post(
        f"/api/v1/member/orders/{order_body['id']}/pay/online",
        headers=mheaders,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["pickup_code"]

    detail = client.get(
        f"/api/v1/member/catering/orders/{order_body['id']}",
        headers=mheaders,
    )
    assert detail.status_code == 200
    assert len(detail.json()["items"]) == 1

    refunded = client.post(
        f"/api/v1/member/catering/orders/{order_body['id']}/refund",
        headers=mheaders,
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"
