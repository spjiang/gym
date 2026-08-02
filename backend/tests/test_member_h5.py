"""会员鉴权与门户 API 测试。"""

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member_login(client: TestClient, phone: str) -> dict:
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    code = get_settings().member_otp_mock_code
    verify = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_member_otp_and_staff_token_rejected(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000001", "name": "H5会员", "merchant_id": gym_id},
    ).json()

    bad = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": "13880000001", "code": "000000"},
    )
    assert bad.status_code == 401

    missing = client.post("/api/v1/member/auth/otp/send", json={"phone": "19999999999"})
    assert missing.status_code == 404
    assert missing.json()["code"] == "member_not_found"

    mheaders = _member_login(client, member["phone"])
    me = client.get("/api/v1/member/me", headers=mheaders)
    assert me.status_code == 200
    assert me.json()["id"] == member["id"]

    # 员工 token 不可访问会员接口
    staff_on_member = client.get("/api/v1/member/me", headers=admin_headers)
    assert staff_on_member.status_code == 401

    # 会员 token 不可访问管理接口
    member_on_admin = client.get("/api/v1/merchants", headers=mheaders)
    assert member_on_admin.status_code == 401


def test_member_portal_book_and_purchase(client: TestClient, admin_headers: dict):
    os.environ["ONLINE_PAYMENT_MODE"] = "mock"
    get_settings.cache_clear()

    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13880000002", "name": "购卡客", "merchant_id": gym_id},
    ).json()
    mheaders = _member_login(client, member["phone"])

    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "H5门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "H5月卡",
            "product_type": "term",
            "price": "199.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()

    # 先后台办一张卡以便约团课（约课需生效会籍）
    seed_order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    client.post(
        f"/api/v1/orders/{seed_order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )

    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_h5",
            "password": "Coach@123456",
            "display_name": "H5教练",
            "merchant_id": gym_id,
            "role_codes": ["coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "display_name": "H5教练",
        },
    ).json()
    course = client.post(
        "/api/v1/group-courses",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "燃脂操",
            "default_capacity": 10,
            "book_ahead_minutes": 0,
            "cancel_ahead_minutes": 0,
        },
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    session = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
            "capacity": 10,
        },
    ).json()

    sessions = client.get(
        f"/api/v1/member/group-sessions?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert sessions.status_code == 200
    assert any(s["id"] == session["id"] for s in sessions.json())

    booking = client.post(
        "/api/v1/member/group-bookings",
        headers=mheaders,
        json={"merchant_id": gym_id, "session_id": session["id"]},
    )
    assert booking.status_code == 200, booking.text
    booking_id = booking.json()["id"]

    cancelled = client.delete(f"/api/v1/member/group-bookings/{booking_id}", headers=mheaders)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # 会员自行购卡并 mock 支付
    order = client.post(
        "/api/v1/member/orders/membership",
        headers=mheaders,
        json={"merchant_id": gym_id, "product_id": product["id"]},
    )
    assert order.status_code == 200, order.text
    paid = client.post(
        f"/api/v1/member/orders/{order.json()['id']}/pay/online",
        headers=mheaders,
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    memberships = client.get(
        f"/api/v1/member/memberships?merchant_id={gym_id}",
        headers=mheaders,
    ).json()
    assert len(memberships) >= 2

    events = client.get("/api/v1/member/access-events", headers=mheaders)
    assert events.status_code == 200

    os.environ["ONLINE_PAYMENT_MODE"] = "unconfigured"
    get_settings.cache_clear()
