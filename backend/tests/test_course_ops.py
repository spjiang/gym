"""私教课包与团课预约测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient


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
            "role_codes": ["coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
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
    ).json()
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
            "role_codes": ["coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff["id"], "display_name": "团课教练"},
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
            "role_codes": ["coach"],
        },
    ).json()
    coach2 = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff2["id"], "display_name": "团课教练2"},
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

    checkin = client.post(
        f"/api/v1/group-bookings/{b3.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert checkin.status_code == 200
    assert checkin.json()["status"] == "attended"
