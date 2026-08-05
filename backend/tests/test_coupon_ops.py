"""优惠券建发、抵扣、核销与退款回退。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _window(days: int = 30) -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return (now - timedelta(hours=1)).isoformat(), (now + timedelta(days=days)).isoformat()


def test_coupon_retail_discount_redeem_and_refund(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts, ends = _window()

    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "满100减20",
            "discount_type": "fixed",
            "threshold_amount": "100.00",
            "fixed_amount": "20.00",
            "applicable_to": "retail",
            "starts_at": starts,
            "ends_at": ends,
            "total_limit": 10,
        },
    )
    assert tpl.status_code == 200, tpl.text
    template_id = tpl.json()["id"]

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13630000001", "name": "券客", "merchant_id": gym_id},
    ).json()

    issued = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": template_id, "member_id": member["id"]},
    )
    assert issued.status_code == 200, issued.text
    coupon_id = issued.json()["id"]
    assert issued.json()["status"] == "unused"

    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "蛋白棒",
            "price": "120.00",
            "unit": "盒",
            "low_stock_threshold": 1,
        },
    ).json()
    client.post(
        f"/api/v1/retail/skus/{sku['id']}/stock/in",
        headers=admin_headers,
        json={"quantity": 5},
    )

    cheap = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "毛巾",
            "price": "50.00",
            "unit": "条",
            "low_stock_threshold": 1,
        },
    ).json()
    client.post(
        f"/api/v1/retail/skus/{cheap['id']}/stock/in",
        headers=admin_headers,
        json={"quantity": 5},
    )
    below = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": cheap["id"], "quantity": 1}],
            "member_coupon_id": coupon_id,
        },
    )
    assert below.status_code == 400
    assert below.json()["code"] == "coupon_threshold"

    order = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku["id"], "quantity": 1}],
            "member_coupon_id": coupon_id,
        },
    )
    assert order.status_code == 200, order.text
    assert order.json()["amount"] == "100.00"
    order_id = order.json()["id"]

    coupons = client.get(
        f"/api/v1/coupons/member-coupons?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert coupons[0]["status"] == "unused"

    paid = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    coupons = client.get(
        f"/api/v1/coupons/member-coupons?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert coupons[0]["status"] == "used"
    assert coupons[0]["used_order_id"] == order_id

    refunded = client.post(f"/api/v1/orders/{order_id}/refund", headers=admin_headers)
    assert refunded.status_code == 200, refunded.text
    coupons = client.get(
        f"/api/v1/coupons/member-coupons?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert coupons[0]["status"] == "unused"
    assert coupons[0]["used_order_id"] is None


def test_coupon_membership_percent(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts, ends = _window()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13630000002", "name": "折扣客", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "券门", "merchant_id": gym_id},
    ).json()

    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "办卡9折",
            "discount_type": "percent",
            "threshold_amount": "0",
            "percent_off": 10,
            "applicable_to": "membership",
            "starts_at": starts,
            "ends_at": ends,
        },
    )
    assert tpl.status_code == 200, tpl.text
    coupon = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": tpl.json()["id"], "member_id": member["id"]},
    ).json()

    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "月卡券测",
            "product_type": "term",
            "price": "300.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()

    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={
            "member_id": member["id"],
            "product_id": product["id"],
            "merchant_id": gym_id,
            "member_coupon_id": coupon["id"],
        },
    )
    assert order.status_code == 200, order.text
    assert order.json()["amount"] == "270.00"
