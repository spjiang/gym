"""会员端餐饮闭环测试。"""

import os

from fastapi.testclient import TestClient

from app.core.config import get_settings
from tests.test_agreements import enable_agreement


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
    # 会员仅关联健身房，未关联清吧；门户仍应展示站点下全部商户
    mheaders = _member_login(client, "13880000091")
    me = client.get("/api/v1/member/me", headers=mheaders).json()
    assert "merchants" in me
    all_site_ids = {m["id"] for m in merchants}
    all_site_ids.add(bar["id"])
    visible_ids = {m["id"] for m in me["merchants"]}
    assert visible_ids >= {gym_id, bar["id"]}
    assert visible_ids >= all_site_ids
    assert gym_id in me["merchant_ids"]
    assert bar["id"] not in me["merchant_ids"]


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

    dish = client.get(
        f"/api/v1/member/catering/menu/{item_id}",
        params={"merchant_id": bar_id},
        headers=mheaders,
    )
    assert dish.status_code == 200, dish.text
    assert dish.json()["id"] == item_id
    assert dish.json()["name"] == "特调气泡水"

    missing = client.get(
        "/api/v1/member/catering/menu/999999",
        params={"merchant_id": bar_id},
        headers=mheaders,
    )
    assert missing.status_code == 404

    desk = client.post(
        "/api/v1/catering/tables",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "A3"},
    )
    assert desk.status_code == 200, desk.text

    enable_agreement(client, admin_headers, bar_id, "dining", title="观野BAR点餐须知")
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
    assert paid.json()["dining_status"] == "preparing"

    blocked = client.post(
        f"/api/v1/member/catering/orders/{order_body['id']}/cancel",
        headers=mheaders,
    )
    assert blocked.status_code == 400

    kitchen = client.post(
        f"/api/v1/catering/orders/{order_body['id']}/ready",
        headers=admin_headers,
    )
    assert kitchen.status_code == 200, kitchen.text
    assert kitchen.json()["dining_status"] == "ready"

    detail = client.get(
        f"/api/v1/member/catering/orders/{order_body['id']}",
        headers=mheaders,
    )
    assert detail.status_code == 200
    assert detail.json()["dining_status"] == "ready"
    assert len(detail.json()["items"]) == 1

    # 会员不可自助退；管理端退款
    member_refund = client.post(
        f"/api/v1/member/catering/orders/{order_body['id']}/refund",
        headers=mheaders,
    )
    assert member_refund.status_code == 404

    refunded = client.post(
        f"/api/v1/orders/{order_body['id']}/refund",
        headers=admin_headers,
        json={"channel": "wechat_original", "reason": "测试退款"},
    )
    assert refunded.status_code == 200, refunded.text
    assert refunded.json()["status"] == "refunded"


def test_member_dining_quote_coupon_and_downline_discount(client: TestClient, admin_headers: dict):
    from datetime import datetime, timedelta, timezone

    os.environ["ONLINE_PAYMENT_MODE"] = "mock"
    get_settings.cache_clear()

    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar_type = next(t for t in types if t["code"] == "bar")
    bar = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar_type["id"],
            "name": "点餐折扣清吧",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()
    bar_id = bar["id"]
    item = client.post(
        "/api/v1/catering/menu-items",
        headers=admin_headers,
        json={"merchant_id": bar_id, "name": "精酿啤酒", "category": "酒水", "price": "38.00"},
    ).json()

    now = datetime.now(timezone.utc)
    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": bar_id,
            "name": "满20减5",
            "discount_type": "fixed",
            "threshold_amount": "20.00",
            "fixed_amount": "5.00",
            "applicable_to": "dining",
            "starts_at": (now - timedelta(hours=1)).isoformat(),
            "ends_at": (now + timedelta(days=30)).isoformat(),
            "claimable": True,
            "per_member_limit": 2,
        },
    )
    assert tpl.status_code == 200, tpl.text

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000093", "name": "用券客", "merchant_id": bar_id},
    ).json()
    issued = client.post(
        "/api/v1/coupons/issue",
        headers=admin_headers,
        json={"merchant_id": bar_id, "template_id": tpl.json()["id"], "member_id": member["id"]},
    )
    assert issued.status_code == 200, issued.text
    coupon_id = issued.json()["id"]
    mheaders = _member_login(client, member["phone"])

    quote = client.post(
        "/api/v1/member/catering/quote",
        headers=mheaders,
        json={"merchant_id": bar_id, "items": [{"menu_item_id": item["id"], "quantity": 1}]},
    )
    assert quote.status_code == 200, quote.text
    assert quote.json()["original_amount"] == "38.00"
    assert quote.json()["payable"] == "38.00"
    assert any(c["id"] == coupon_id and c["eligible"] for c in quote.json()["coupons"])

    quoted = client.post(
        "/api/v1/member/catering/quote",
        headers=mheaders,
        json={
            "merchant_id": bar_id,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "member_coupon_id": coupon_id,
        },
    )
    assert quoted.status_code == 200, quoted.text
    assert quoted.json()["coupon_discount_amount"] == "5.00"
    assert quoted.json()["payable"] == "33.00"

    enable_agreement(client, admin_headers, bar_id, "dining", title="观野BAR点餐须知")
    order = client.post(
        "/api/v1/member/catering/checkout",
        headers=mheaders,
        json={
            "merchant_id": bar_id,
            "items": [{"menu_item_id": item["id"], "quantity": 1}],
            "member_coupon_id": coupon_id,
        },
    )
    assert order.status_code == 200, order.text
    assert order.json()["original_amount"] == "38.00"
    assert order.json()["amount"] == "33.00"

    cancelled = client.post(
        f"/api/v1/member/catering/orders/{order.json()['id']}/cancel",
        headers=mheaders,
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"

    again = client.post(
        f"/api/v1/member/catering/orders/{order.json()['id']}/cancel",
        headers=mheaders,
    )
    assert again.status_code == 400

    mine = client.get(
        "/api/v1/member/coupons",
        params={"merchant_id": bar_id, "system": "catering"},
        headers=mheaders,
    )
    assert mine.status_code == 200
    restored = next(x for x in mine.json() if x["id"] == coupon_id)
    assert restored["status"] == "unused"

    settings = client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={"default_downline_discount_rate": "0.10", "default_rebate_rate": "0.05"},
    )
    assert settings.status_code == 200, settings.text
    upline = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000094", "name": "推广人", "merchant_id": bar_id},
    ).json()
    promo = client.get(f"/api/v1/members/{upline['id']}/promotion", headers=admin_headers)
    assert promo.status_code == 200, promo.text
    code = promo.json()["code"]
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": "13880000095", "merchant_id": bar_id})
    assert send.status_code == 200
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={
            "phone": "13880000095",
            "code": get_settings().member_otp_mock_code,
            "merchant_id": bar_id,
            "referral_code": code,
        },
    )
    assert verify.status_code == 200, verify.text
    down_headers = {"Authorization": f"Bearer {verify.json()['access_token']}"}
    down_quote = client.post(
        "/api/v1/member/catering/quote",
        headers=down_headers,
        json={"merchant_id": bar_id, "items": [{"menu_item_id": item["id"], "quantity": 1}]},
    )
    assert down_quote.status_code == 200, down_quote.text
    assert down_quote.json()["original_amount"] == "38.00"
    assert down_quote.json()["promotion_discount_amount"] == "3.80"
    assert down_quote.json()["payable"] == "34.20"
