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
            "per_member_limit": 2,
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
    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    membership_id = client.get(
        "/api/v1/memberships",
        headers=admin_headers,
        params={"merchant_id": gym_id, "member_id": member["id"]},
    ).json()["items"][0]["id"]
    renew_coupon = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": tpl.json()["id"], "member_id": member["id"]},
    ).json()
    renew_order = client.post(
        "/api/v1/memberships/renew",
        headers=admin_headers,
        json={
            "membership_id": membership_id,
            "product_id": product["id"],
            "merchant_id": gym_id,
            "member_coupon_id": renew_coupon["id"],
        },
    )
    assert renew_order.status_code == 200, renew_order.text
    assert renew_order.json()["amount"] == "270.00"


def test_coupon_issue_batch_to_merchant_members(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts, ends = _window()
    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "商户群发券",
            "discount_type": "fixed",
            "threshold_amount": "10.00",
            "fixed_amount": "5.00",
            "applicable_to": "both",
            "starts_at": starts,
            "ends_at": ends,
        },
    )
    assert tpl.status_code == 200, tpl.text
    created = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13630000088", "name": "群发会员", "merchant_id": gym_id},
    )
    assert created.status_code == 200, created.text
    r = client.post(
        "/api/v1/coupons/issue-batch",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": tpl.json()["id"]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["issued"] >= 1
    assert r.json()["total"] >= r.json()["issued"]


def test_coupon_template_search_edit_and_member_coupon_ops(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts, ends = _window()
    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "可检索满减券",
            "discount_type": "fixed",
            "threshold_amount": "50.00",
            "fixed_amount": "8.00",
            "applicable_to": "retail",
            "starts_at": starts,
            "ends_at": ends,
            "total_limit": 20,
        },
    )
    assert tpl.status_code == 200, tpl.text
    tid = tpl.json()["id"]

    listed = client.get(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        params={"q": "可检索", "discount_type": "fixed", "is_active": True},
    )
    assert listed.status_code == 200
    assert any(x["id"] == tid for x in listed.json()["items"])

    patched = client.patch(
        f"/api/v1/coupons/templates/{tid}",
        headers=admin_headers,
        json={"name": "可检索满减券改名", "threshold_amount": "60.00"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["name"] == "可检索满减券改名"
    assert patched.json()["threshold_amount"] == "60.00"

    detail = client.get(f"/api/v1/coupons/templates/{tid}", headers=admin_headers)
    assert detail.status_code == 200
    assert detail.json()["name"] == "可检索满减券改名"

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13630000077", "name": "持券编辑客", "merchant_id": gym_id},
    ).json()
    issued = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": gym_id, "template_id": tid, "member_id": member["id"]},
    )
    assert issued.status_code == 200, issued.text
    cid = issued.json()["id"]

    later = (datetime.now(timezone.utc) + timedelta(days=60)).isoformat()
    edited = client.patch(
        f"/api/v1/coupons/member-coupons/{cid}",
        headers=admin_headers,
        json={"ends_at": later},
    )
    assert edited.status_code == 200, edited.text

    got = client.get(f"/api/v1/coupons/member-coupons/{cid}", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["template_name"] == "可检索满减券改名"
    assert got.json()["discount_type"] == "fixed"
    assert got.json()["threshold_amount"] == "60.00"
    assert got.json()["fixed_amount"] == "8.00"
    assert got.json()["applicable_to"] == "retail"

    listed = client.get(
        "/api/v1/coupons/member-coupons",
        headers=admin_headers,
        params={"merchant_id": gym_id, "member_id": member["id"]},
    )
    assert listed.status_code == 200
    item = next(x for x in listed.json()["items"] if x["id"] == cid)
    assert item["template_name"] == "可检索满减券改名"
    assert item["discount_type"] == "fixed"
    assert item["threshold_amount"] == "60.00"

    voided = client.post(f"/api/v1/coupons/member-coupons/{cid}/deactivate", headers=admin_headers)
    assert voided.status_code == 200, voided.text
    assert voided.json()["status"] == "void"

    blocked = client.patch(
        f"/api/v1/coupons/member-coupons/{cid}",
        headers=admin_headers,
        json={"ends_at": later},
    )
    assert blocked.status_code == 400
