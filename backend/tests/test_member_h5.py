"""会员鉴权与门户 API 测试。"""

import os
from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import new_coach_member

from app.core.config import get_settings
from tests.test_agreements import enable_agreement


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
    assert missing.status_code == 200
    # 未注册也可发码；校验后自动注册为平台来源
    code = get_settings().member_otp_mock_code
    reg = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": "19999999999", "code": code},
    )
    assert reg.status_code == 200, reg.text
    mheaders_new = {"Authorization": f"Bearer {reg.json()['access_token']}"}
    me_new = client.get("/api/v1/member/me", headers=mheaders_new)
    assert me_new.status_code == 200
    assert me_new.json()["acquisition_source"] == "platform"

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
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": new_coach_member(client, admin_headers, gym_id)["id"],
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
    listed = sessions.json()
    hit = next(s for s in listed if s["id"] == session["id"])
    assert hit["course_name"] == "燃脂操"
    assert hit["coach_name"] == "H5教练"
    assert "remaining" in hit

    started = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(),
            "ends_at": datetime.now(timezone.utc).isoformat(),
            "capacity": 10,
        },
    ).json()
    listed_again = client.get(
        f"/api/v1/member/group-sessions?merchant_id={gym_id}",
        headers=mheaders,
    ).json()
    assert all(s["id"] != started["id"] for s in listed_again)

    detail = client.get(f"/api/v1/member/group-sessions/{session['id']}", headers=mheaders)
    assert detail.status_code == 200, detail.text
    assert detail.json()["course_name"] == "燃脂操"
    assert detail.json()["coach_id"] == coach["id"]

    coach_detail = client.get(f"/api/v1/member/coaches/{coach['id']}", headers=mheaders)
    assert coach_detail.status_code == 200, coach_detail.text
    assert coach_detail.json()["display_name"] == "H5教练"
    assert "pt_commission_rate" not in coach_detail.json()

    home = client.get(f"/api/v1/member/home?merchant_id={gym_id}", headers=mheaders)
    assert home.status_code == 200, home.text
    home_body = home.json()
    assert home_body["merchant"]["id"] == gym_id
    assert any(c["id"] == coach["id"] for c in home_body["coaches"])
    assert any(p["id"] == product["id"] for p in home_body["memberships"])
    assert any(s["id"] == session["id"] for s in home_body["sessions"])

    booking = client.post(
        "/api/v1/member/group-bookings",
        headers=mheaders,
        json={"merchant_id": gym_id, "session_id": session["id"]},
    )
    assert booking.status_code == 200, booking.text
    assert booking.json()["course_name"] == "燃脂操"
    booking_id = booking.json()["id"]

    cancelled = client.delete(f"/api/v1/member/group-bookings/{booking_id}", headers=mheaders)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    # 会员自行购卡并 mock 支付
    enable_agreement(client, admin_headers, gym_id, "membership")
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
