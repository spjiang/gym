"""站内通知写入与查询测试。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_order_paid_writes_notification(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000911", "name": "通知会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "order_type": "retail",
            "title": "水瓶",
            "amount": "10.00",
        },
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    notes = client.get(f"/api/v1/notifications?merchant_id={gym_id}", headers=admin_headers).json()
    assert any(n["event_type"] == "order.paid" and n["member_id"] == member["id"] for n in notes)


def test_membership_fulfill_writes_notification(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13900000912", "name": "开卡通知", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "开卡门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡通知",
            "product_type": "term",
            "duration_days": 30,
            "price": "199.00",
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
    paid = client.post(
        f"/api/v1/orders/{purchase.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    notes = client.get(f"/api/v1/notifications?merchant_id={gym_id}", headers=admin_headers).json()
    assert any(
        n["event_type"] == "membership.fulfilled" and n["member_id"] == member["id"] for n in notes
    )
