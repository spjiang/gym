"""私教课包与团课预约测试。"""

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi.testclient import TestClient

from tests.conftest import new_coach_member


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _ensure_membership(client: TestClient, headers: dict, gym_id: int, member_id: int, phone_suffix: str):
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": f"课门{phone_suffix}", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "name": f"月卡{phone_suffix}",
            "product_type": "term",
            "price": "100.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=headers,
        json={"member_id": member_id, "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )


def test_pt_purchase_fulfill_and_consume(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_pt1",
            "password": "Coach@123456",
            "display_name": "私教甲",
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
            "display_name": "私教甲",
            "specialties": "增肌",
        },
    )
    assert coach.status_code == 200, coach.text

    product = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "10次私教",
            "price": "2000.00",
            "session_count": 2,
            "valid_days": 90,
            "all_coaches": True,
        },
    )
    assert product.status_code == 200, product.text

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000001", "name": "课包会员", "merchant_id": gym_id},
    ).json()

    order = client.post(
        "/api/v1/pt-packages/purchase",
        headers=admin_headers,
        json={"merchant_id": gym_id, "member_id": member["id"], "product_id": product.json()["id"]},
    )
    assert order.status_code == 200, order.text
    assert order.json()["order_type"] == "pt_package"

    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    packages = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"]
    assert len(packages) == 1
    assert packages[0]["status"] == "active"
    assert packages[0]["remaining_sessions"] == 2
    pkg_id = packages[0]["id"]

    c1 = client.post(f"/api/v1/pt-packages/{pkg_id}/consume", headers=admin_headers)
    assert c1.status_code == 200
    assert c1.json()["remaining_sessions"] == 1
    c2 = client.post(f"/api/v1/pt-packages/{pkg_id}/consume", headers=admin_headers)
    assert c2.status_code == 200
    assert c2.json()["status"] == "exhausted"
    c3 = client.post(f"/api/v1/pt-packages/{pkg_id}/consume", headers=admin_headers)
    assert c3.status_code == 400

    logs = client.get(f"/api/v1/pt-packages/{pkg_id}/consumes", headers=admin_headers)
    assert logs.status_code == 200, logs.text
    assert len(logs.json()) == 2
    assert logs.json()[0]["sessions"] == 1
    assert logs.json()[0]["remaining_after"] == 0
    assert logs.json()[1]["remaining_after"] == 1
    assert logs.json()[0]["actor_name"]

    today = datetime.now(ZoneInfo("Asia/Shanghai")).date().isoformat()
    by_today = client.get(
        f"/api/v1/pt-packages/{pkg_id}/consumes?from_date={today}&to_date={today}",
        headers=admin_headers,
    )
    assert by_today.status_code == 200, by_today.text
    assert len(by_today.json()) == 2
    miss = client.get(
        f"/api/v1/pt-packages/{pkg_id}/consumes?from_date=2000-01-01&to_date=2000-01-02",
        headers=admin_headers,
    )
    assert miss.status_code == 200
    assert miss.json() == []


def test_pt_package_search_detail_and_patch(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    product = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索私教10节",
            "price": "1800.00",
            "session_count": 10,
            "valid_days": 60,
            "all_coaches": True,
        },
    )
    assert product.status_code == 200, product.text
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000021", "name": "课包检索会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/pt-packages/purchase",
        headers=admin_headers,
        json={"merchant_id": gym_id, "member_id": member["id"], "product_id": product.json()["id"]},
    )
    assert order.status_code == 200, order.text
    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    by_name = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&q=检索私教",
        headers=admin_headers,
    )
    assert by_name.status_code == 200, by_name.text
    assert by_name.json()["total"] >= 1
    pkg = by_name.json()["items"][0]
    assert pkg["product"]["name"] == "检索私教10节"
    pkg_id = pkg["id"]

    by_member = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&q=课包检索",
        headers=admin_headers,
    )
    assert any(x["id"] == pkg_id for x in by_member.json()["items"])

    by_product = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&product_id={product.json()['id']}",
        headers=admin_headers,
    )
    assert any(x["id"] == pkg_id for x in by_product.json()["items"])

    miss = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&q=不存在的课包名xyz",
        headers=admin_headers,
    )
    assert all(x["id"] != pkg_id for x in miss.json()["items"])

    detail = client.get(f"/api/v1/pt-packages/{pkg_id}", headers=admin_headers)
    assert detail.status_code == 200, detail.text
    assert detail.json()["remaining_sessions"] == 10
    assert detail.json()["member"]["name"] == "课包检索会员"

    patched = client.patch(
        f"/api/v1/pt-packages/{pkg_id}",
        headers=admin_headers,
        json={"remaining_sessions": 8, "status": "active"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["remaining_sessions"] == 8
    assert patched.json()["status"] == "active"

    exhausted = client.patch(
        f"/api/v1/pt-packages/{pkg_id}",
        headers=admin_headers,
        json={"remaining_sessions": 0},
    )
    assert exhausted.status_code == 200, exhausted.text
    assert exhausted.json()["status"] == "exhausted"
    assert exhausted.json()["remaining_sessions"] == 0


def test_group_booking_membership_full_cancel(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_g1",
            "password": "Coach@123456",
            "display_name": "团课教练",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff["id"], "member_id": new_coach_member(client, admin_headers, gym_id)["id"], "display_name": "团课教练"},
    ).json()

    # 停用后不可排场
    client.post(f"/api/v1/coaches/{coach['id']}/deactivate", headers=admin_headers)
    course = client.post(
        "/api/v1/group-courses",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "燃脂操",
            "default_capacity": 1,
            "book_ahead_minutes": 0,
            "cancel_ahead_minutes": 0,
        },
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    ends = starts + timedelta(hours=1)
    bad = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "capacity": 1,
            "room": "A厅",
        },
    )
    assert bad.status_code == 400

    # 重新启用：再创建教练档案（停用后不可用；用新教练）
    staff2 = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_g2",
            "password": "Coach@123456",
            "display_name": "团课教练2",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach2 = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff2["id"], "member_id": new_coach_member(client, admin_headers, gym_id)["id"], "display_name": "团课教练2"},
    ).json()

    session = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach2["id"],
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "capacity": 1,
            "room": "A厅",
        },
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["id"]

    # 改派
    re = client.post(
        f"/api/v1/group-sessions/{session_id}/reassign",
        headers=admin_headers,
        json={"coach_id": coach2["id"]},
    )
    assert re.status_code == 200

    listed = client.get(
        f"/api/v1/group-sessions?merchant_id={gym_id}&q=燃脂&page=1&page_size=10",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    assert listed.json()["total"] >= 1
    assert any(x["id"] == session_id for x in listed.json()["items"])

    starts_at = datetime.fromisoformat(session.json()["starts_at"].replace("Z", "+00:00"))
    on_date = starts_at.astimezone(ZoneInfo("Asia/Shanghai")).date().isoformat()
    by_date = client.get(
        f"/api/v1/group-sessions?merchant_id={gym_id}&course_id={course['id']}&coach_id={coach2['id']}&on_date={on_date}",
        headers=admin_headers,
    )
    assert by_date.status_code == 200, by_date.text
    assert any(x["id"] == session_id for x in by_date.json()["items"])
    miss = client.get(
        f"/api/v1/group-sessions?merchant_id={gym_id}&on_date=2000-01-01",
        headers=admin_headers,
    )
    assert miss.status_code == 200
    assert all(x["id"] != session_id for x in miss.json()["items"])

    patched = client.patch(
        f"/api/v1/group-sessions/{session_id}",
        headers=admin_headers,
        json={"room": "团操房 B"},
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["room"] == "团操房 B"
    assert patched.json()["capacity"] == 1

    m1 = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000011", "name": "有会籍", "merchant_id": gym_id},
    ).json()
    m2 = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000012", "name": "无会籍", "merchant_id": gym_id},
    ).json()
    m3 = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000013", "name": "第二人", "merchant_id": gym_id},
    ).json()
    _ensure_membership(client, admin_headers, gym_id, m1["id"], "a")
    _ensure_membership(client, admin_headers, gym_id, m3["id"], "b")

    deny = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": m2["id"]},
    )
    assert deny.status_code == 400
    assert deny.json()["code"] == "membership_required"

    b1 = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": m1["id"]},
    )
    assert b1.status_code == 200, b1.text

    full = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": m3["id"]},
    )
    assert full.status_code == 400
    assert full.json()["code"] == "session_full"

    cancel = client.post(
        f"/api/v1/group-bookings/{b1.json()['id']}/cancel",
        headers=admin_headers,
        json={"force": True},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    b3 = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": m3["id"]},
    )
    assert b3.status_code == 200, b3.text

    too_early = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert too_early.status_code == 400, too_early.text
    assert too_early.json()["code"] in {"checkin_too_early", "checkin_wrong_day"}

    now = datetime.now(timezone.utc)
    moved = client.patch(
        f"/api/v1/group-sessions/{session_id}",
        headers=admin_headers,
        json={
            "starts_at": (now + timedelta(minutes=20)).isoformat(),
            "ends_at": (now + timedelta(minutes=80)).isoformat(),
        },
    )
    assert moved.status_code == 200, moved.text

    checkin = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert checkin.status_code == 200
    assert checkin.json()["status"] == "attended"

    revise = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "no_show"},
    )
    assert revise.status_code == 200, revise.text
    assert revise.json()["status"] == "no_show"
    back = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert back.status_code == 200
    assert back.json()["status"] == "attended"

    past = datetime.now(timezone.utc)
    ended = client.patch(
        f"/api/v1/group-sessions/{session_id}",
        headers=admin_headers,
        json={
            "starts_at": (past - timedelta(hours=2)).isoformat(),
            "ends_at": (past - timedelta(hours=1)).isoformat(),
        },
    )
    assert ended.status_code == 200, ended.text
    late = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert late.status_code == 400, late.text
    assert late.json()["code"] == "checkin_too_late"


def test_pt_product_search_and_reactivate(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    ten = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索私教10节商品",
            "price": "2980.00",
            "session_count": 10,
            "valid_days": 90,
            "all_coaches": True,
        },
    )
    assert ten.status_code == 200, ten.text
    twenty = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "检索私教20节商品",
            "price": "5280.00",
            "session_count": 20,
            "valid_days": 180,
            "all_coaches": True,
        },
    )
    assert twenty.status_code == 200, twenty.text
    ten_id = ten.json()["id"]
    twenty_id = twenty.json()["id"]

    off = client.post(f"/api/v1/pt-products/{twenty_id}/deactivate", headers=admin_headers)
    assert off.status_code == 200
    assert off.json()["is_active"] is False

    by_name = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&q=20节商品",
        headers=admin_headers,
    )
    assert {x["id"] for x in by_name.json()["items"]} == {twenty_id}

    by_id = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&q={ten_id}",
        headers=admin_headers,
    )
    assert any(x["id"] == ten_id for x in by_id.json()["items"])

    inactive = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&is_active=false",
        headers=admin_headers,
    )
    assert twenty_id in {x["id"] for x in inactive.json()["items"]}
    assert ten_id not in {x["id"] for x in inactive.json()["items"]}

    cheap = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&price_max=3000",
        headers=admin_headers,
    )
    cheap_ids = {x["id"] for x in cheap.json()["items"]}
    assert ten_id in cheap_ids
    assert twenty_id not in cheap_ids

    sessions = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&session_min=15",
        headers=admin_headers,
    )
    assert twenty_id in {x["id"] for x in sessions.json()["items"]}
    assert ten_id not in {x["id"] for x in sessions.json()["items"]}

    days = client.get(
        f"/api/v1/pt-products?merchant_id={gym_id}&valid_days_max=100",
        headers=admin_headers,
    )
    day_ids = {x["id"] for x in days.json()["items"]}
    assert ten_id in day_ids
    assert twenty_id not in day_ids

    on = client.post(f"/api/v1/pt-products/{twenty_id}/activate", headers=admin_headers)
    assert on.status_code == 200, on.text
    assert on.json()["is_active"] is True
    listed = client.get(f"/api/v1/pt-products?merchant_id={gym_id}&q=20节商品", headers=admin_headers)
    assert listed.json()["items"][0]["is_active"] is True


def test_group_session_soft_delete(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_del1",
            "password": "Coach@123456",
            "display_name": "删除场次教练",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff["id"], "member_id": new_coach_member(client, admin_headers, gym_id)["id"], "display_name": "删除场次教练"},
    ).json()
    course = client.post(
        "/api/v1/group-courses",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "待删团课",
            "default_capacity": 8,
            "book_ahead_minutes": 0,
            "cancel_ahead_minutes": 0,
        },
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(days=2)
    ends = starts + timedelta(hours=1)
    session = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": ends.isoformat(),
            "capacity": 8,
            "room": "操房删除测",
        },
    )
    assert session.status_code == 200, session.text
    session_id = session.json()["id"]

    missing = client.delete("/api/v1/group-sessions/999999", headers=admin_headers)
    assert missing.status_code == 404

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13610000091", "name": "待取消预约", "merchant_id": gym_id},
    ).json()
    _ensure_membership(client, admin_headers, gym_id, member["id"], "del")
    booked = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": member["id"]},
    )
    assert booked.status_code == 200, booked.text

    deleted = client.delete(f"/api/v1/group-sessions/{session_id}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json()["id"] == session_id
    assert deleted.json()["status"] == "cancelled"

    listed = client.get(
        f"/api/v1/group-sessions?merchant_id={gym_id}&q=操房删除测",
        headers=admin_headers,
    )
    assert listed.status_code == 200, listed.text
    assert any(x["id"] == session_id and x["status"] == "cancelled" for x in listed.json()["items"])

    again = client.delete(f"/api/v1/group-sessions/{session_id}", headers=admin_headers)
    assert again.status_code == 200, again.text
    assert again.json()["status"] == "cancelled"

    bookings = client.get(
        f"/api/v1/group-bookings?merchant_id={gym_id}&session_id={session_id}",
        headers=admin_headers,
    )
    assert bookings.status_code == 200, bookings.text
    assert bookings.json()["items"]
    assert all(x["status"] == "cancelled" for x in bookings.json()["items"])

    rebook = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={"merchant_id": gym_id, "session_id": session_id, "member_id": member["id"]},
    )
    assert rebook.status_code == 400
    assert rebook.json()["code"] == "session_closed"


def test_coach_profile_fields(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "coach_profile_1",
            "password": "Coach@123456",
            "display_name": "档案教练",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    avatar = f"/api/v1/files/{'a' * 32}.jpg"
    gallery = [f"/api/v1/files/{'b' * 32}.png", f"/api/v1/files/{'c' * 32}.webp"]
    created = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": new_coach_member(client, admin_headers, gym_id)["id"],
            "display_name": "林教练",
            "title": "金牌私教",
            "gender": "male",
            "phone": "13800001111",
            "years_experience": 7,
            "hourly_rate": "320.00",
            "specialties": "增肌,体态",
            "certifications": "NSCA-CPT",
            "bio": "专注力量训练。",
            "availability_note": "周二至周日 10:00-21:00",
            "avatar_url": avatar,
            "intro_image_urls": gallery,
        },
    )
    assert created.status_code == 200, created.text
    body = created.json()
    assert body["title"] == "金牌私教"
    assert body["gender"] == "male"
    assert body["avatar_url"] == avatar
    assert body["intro_image_urls"] == gallery
    assert body["member_id"] is not None
    assert body["promotion_code"]
    assert body["years_experience"] == 7

    bad = client.patch(
        f"/api/v1/coaches/{body['id']}",
        headers=admin_headers,
        json={
            "staff_user_id": staff["id"],
            "member_id": new_coach_member(client, admin_headers, gym_id)["id"],
            "display_name": "林教练",
            "avatar_url": "https://example.com/a.jpg",
        },
    )
    assert bad.status_code == 400

    hit = client.get(
        f"/api/v1/coaches?merchant_id={gym_id}&q=金牌&gender=male",
        headers=admin_headers,
    )
    assert hit.status_code == 200, hit.text
    assert any(x["id"] == body["id"] for x in hit.json()["items"])

    patched = client.patch(
        f"/api/v1/coaches/{body['id']}",
        headers=admin_headers,
        json={
            "staff_user_id": staff["id"],
            "member_id": new_coach_member(client, admin_headers, gym_id)["id"],
            "display_name": "林教练",
            "title": "团课+私教",
            "gender": "male",
            "phone": "13800001111",
            "years_experience": 7,
            "hourly_rate": "320.00",
            "specialties": "增肌,体态",
            "certifications": "NSCA-CPT",
            "bio": "专注力量训练。",
            "availability_note": "周二至周日 10:00-21:00",
            "avatar_url": avatar,
            "intro_image_urls": [gallery[0]],
        },
    )
    assert patched.status_code == 200, patched.text
    assert patched.json()["title"] == "团课+私教"
    assert patched.json()["intro_image_urls"] == [gallery[0]]
