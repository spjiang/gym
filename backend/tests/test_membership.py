"""会籍卡种、办卡履约与门禁联动测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _prepare_point_and_member(client: TestClient, headers: dict, gym_id: int):
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": "13700000001", "name": "会籍会员", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": "会籍门", "merchant_id": gym_id},
    ).json()
    client.post(
        "/api/v1/devices",
        headers=headers,
        json={"access_point_id": point["id"], "device_code": "mem-pad", "api_key": "mem-key"},
    )
    return member, point


def test_product_requires_access_points_to_activate(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    r = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡",
            "product_type": "term",
            "price": "299.00",
            "duration_days": 30,
            "access_point_ids": [],
            "is_active": True,
        },
    )
    assert r.status_code == 400


def test_create_product_and_purchase_flow(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member, point = _prepare_point_and_member(client, admin_headers, gym_id)

    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "季卡",
            "product_type": "term",
            "price": "799.00",
            "duration_days": 90,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    product_id = product.json()["id"]

    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product_id, "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    assert order.json()["order_type"] == "membership"
    assert order.json()["status"] == "pending"
    order_id = order.json()["id"]

    paid = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    memberships = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()
    assert len(memberships) == 1
    assert memberships[0]["status"] == "active"
    membership_id = memberships[0]["id"]

    # 通行放行
    ok = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "mem-pad", "X-Device-Key": "mem-key"},
        json={"member_id": member["id"]},
    )
    assert ok.json()["allowed"] is True

    # 续卡延期
    ends_before = memberships[0]["ends_at"]
    renew_order = client.post(
        "/api/v1/memberships/renew",
        headers=admin_headers,
        json={"membership_id": membership_id, "product_id": product_id},
    )
    assert renew_order.status_code == 200
    client.post(
        f"/api/v1/orders/{renew_order.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    after = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()[0]
    assert after["ends_at"] > ends_before

    # 停卡后拒绝
    freeze = client.post(f"/api/v1/memberships/{membership_id}/freeze", headers=admin_headers)
    assert freeze.status_code == 200
    assert freeze.json()["status"] == "frozen"
    denied = client.post(
        "/api/v1/device/access/verify",
        headers={"X-Device-Code": "mem-pad", "X-Device-Key": "mem-key"},
        json={"member_id": member["id"]},
    )
    assert denied.json()["allowed"] is False
