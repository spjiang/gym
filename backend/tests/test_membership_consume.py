"""会籍销次 / 储值扣费与作废测试。"""

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _buy(client: TestClient, headers: dict, gym_id: int, member_id: int, product_id: int) -> int:
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=headers,
        json={"member_id": member_id, "product_id": product_id, "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    items = client.get(
        f"/api/v1/memberships?merchant_id={gym_id}&member_id={member_id}",
        headers=headers,
    ).json()["items"]
    return items[0]["id"]


def test_count_card_consume_flow(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "销次门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "次卡2次",
            "product_type": "count",
            "price": "200.00",
            "session_count": 2,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13520000001", "name": "次卡会员", "merchant_id": gym_id},
    ).json()
    membership_id = _buy(client, admin_headers, gym_id, member["id"], product.json()["id"])

    first = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"sessions": 1, "note": "前台销次"},
    )
    assert first.status_code == 200, first.text
    assert first.json()["membership"]["remaining_sessions"] == 1
    assert first.json()["consumption"]["kind"] == "session"
    assert first.json()["consumption"]["sessions"] == 1
    assert first.json()["consumption"]["actor_name"]

    second = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"sessions": 1},
    )
    assert second.status_code == 200, second.text
    # 次数耗尽自动过期
    assert second.json()["membership"]["remaining_sessions"] == 0
    assert second.json()["membership"]["status"] == "expired"

    third = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"sessions": 1},
    )
    assert third.status_code == 400
    assert third.json()["code"] == "invalid_state"

    logs = client.get(
        f"/api/v1/memberships/{membership_id}/consumptions",
        headers=admin_headers,
    )
    assert logs.status_code == 200, logs.text
    assert logs.json()["total"] == 2
    assert logs.json()["items"][0]["remaining_sessions_after"] == 0


def test_value_card_consume_and_void(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "储值门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "储值卡100",
            "product_type": "value",
            "price": "100.00",
            "stored_value": "100.00",
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13520000002", "name": "储值会员", "merchant_id": gym_id},
    ).json()
    membership_id = _buy(client, admin_headers, gym_id, member["id"], product.json()["id"])

    need_amount = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"sessions": 1},
    )
    assert need_amount.status_code == 400
    assert need_amount.json()["code"] == "invalid_amount"

    charged = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"amount": "30.00", "note": "私教单次"},
    )
    assert charged.status_code == 200, charged.text
    assert charged.json()["membership"]["balance"] == "70.00"
    assert charged.json()["consumption"]["kind"] == "value"

    over = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"amount": "1000.00"},
    )
    assert over.status_code == 400
    assert over.json()["code"] == "insufficient_balance"

    voided = client.post(f"/api/v1/memberships/{membership_id}/void", headers=admin_headers)
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "void"

    after_void = client.post(
        f"/api/v1/memberships/{membership_id}/consume",
        headers=admin_headers,
        json={"amount": "10.00"},
    )
    assert after_void.status_code == 400
    assert after_void.json()["code"] == "invalid_state"


def test_term_card_rejects_consume(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "期限门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "期限月卡",
            "product_type": "term",
            "price": "199.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13520000003", "name": "期限会员", "merchant_id": gym_id},
    ).json()
    membership_id = _buy(client, admin_headers, gym_id, member["id"], product["id"])

    resp = client.post(f"/api/v1/memberships/{membership_id}/consume", headers=admin_headers)
    assert resp.status_code == 400
    assert resp.json()["code"] == "unsupported_product"
