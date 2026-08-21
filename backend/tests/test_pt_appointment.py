"""私教 1v1 预约排期、核销与冲突校验测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import new_coach_member


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _coach(client: TestClient, headers: dict, gym_id: int, username: str, name: str) -> dict:
    staff = client.post(
        "/api/v1/staff",
        headers=headers,
        json={
            "username": username,
            "password": "Coach@123456",
            "display_name": name,
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": new_coach_member(client, headers, gym_id)["id"],
            "display_name": name,
            "hourly_rate": "300.00",
        },
    )
    assert coach.status_code == 200, coach.text
    return coach.json()


def _member_with_package(
    client: TestClient,
    headers: dict,
    gym_id: int,
    phone: str,
    name: str,
    *,
    session_count: int = 2,
) -> tuple[dict, int]:
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": phone, "name": name, "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/pt-products",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "name": f"私教{session_count}节-{phone[-4:]}",
            "price": "2000.00",
            "session_count": session_count,
            "valid_days": 90,
            "all_coaches": True,
        },
    ).json()
    order = client.post(
        "/api/v1/pt-packages/purchase",
        headers=headers,
        json={"merchant_id": gym_id, "member_id": member["id"], "product_id": product["id"]},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    packages = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&member_id={member['id']}",
        headers=headers,
    ).json()["items"]
    return member, packages[0]["id"]


def test_appointment_create_complete_and_consume(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    coach = _coach(client, admin_headers, gym_id, "pt_coach_a", "预约教练A")
    member, package_id = _member_with_package(
        client, admin_headers, gym_id, "13540000001", "预约会员"
    )

    available = client.get(
        f"/api/v1/pt-appointments/available-packages?member_id={member['id']}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert available.status_code == 200, available.text
    assert [p["id"] for p in available.json()] == [package_id]
    assert available.json()[0]["remaining_sessions"] == 2

    starts = datetime.now(timezone.utc) + timedelta(days=1)
    created = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "package_id": package_id,
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
            "location": "私教区",
        },
    )
    assert created.status_code == 200, created.text
    appointment = created.json()
    assert appointment["status"] == "booked"
    assert appointment["coach_name"] == "预约教练A"
    assert appointment["package_remaining_sessions"] == 2

    # 同教练时段冲突
    other_member, other_package = _member_with_package(
        client, admin_headers, gym_id, "13540000002", "冲突会员"
    )
    conflict = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": other_member["id"],
            "coach_id": coach["id"],
            "package_id": other_package,
            "starts_at": (starts + timedelta(minutes=30)).isoformat(),
            "ends_at": (starts + timedelta(minutes=90)).isoformat(),
        },
    )
    assert conflict.status_code == 409
    assert conflict.json()["code"] == "coach_busy"

    moved = client.patch(
        f"/api/v1/pt-appointments/{appointment['id']}",
        headers=admin_headers,
        json={
            "starts_at": (starts + timedelta(days=1)).isoformat(),
            "ends_at": (starts + timedelta(days=1, hours=1)).isoformat(),
            "note": "会员申请改期",
        },
    )
    assert moved.status_code == 200, moved.text
    assert moved.json()["note"] == "会员申请改期"

    done = client.post(
        f"/api/v1/pt-appointments/{appointment['id']}/complete", headers=admin_headers
    )
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "completed"
    assert done.json()["completed_at"]
    assert done.json()["package_remaining_sessions"] == 1

    repeat = client.post(
        f"/api/v1/pt-appointments/{appointment['id']}/complete", headers=admin_headers
    )
    assert repeat.status_code == 400
    assert repeat.json()["code"] == "invalid_state"

    logs = client.get(f"/api/v1/pt-packages/{package_id}/consumes", headers=admin_headers)
    assert logs.status_code == 200
    assert len(logs.json()) == 1


def test_appointment_cancel_and_no_show(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    coach = _coach(client, admin_headers, gym_id, "pt_coach_b", "预约教练B")
    member, package_id = _member_with_package(
        client, admin_headers, gym_id, "13540000003", "取消会员"
    )
    starts = datetime.now(timezone.utc) + timedelta(days=2)

    booked = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "package_id": package_id,
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
        },
    ).json()
    cancelled = client.post(
        f"/api/v1/pt-appointments/{booked['id']}/cancel",
        headers=admin_headers,
        json={"reason": "会员出差"},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    assert cancelled.json()["cancel_reason"] == "会员出差"
    # 取消不扣课时
    assert cancelled.json()["package_remaining_sessions"] == 2

    second = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "package_id": package_id,
            "starts_at": (starts + timedelta(days=1)).isoformat(),
            "ends_at": (starts + timedelta(days=1, hours=1)).isoformat(),
        },
    ).json()
    no_show = client.post(
        f"/api/v1/pt-appointments/{second['id']}/no-show",
        headers=admin_headers,
        json={"consume_session": True},
    )
    assert no_show.status_code == 200, no_show.text
    assert no_show.json()["status"] == "no_show"
    assert no_show.json()["package_remaining_sessions"] == 1


def test_appointment_package_capacity_and_filters(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    coach = _coach(client, admin_headers, gym_id, "pt_coach_c", "预约教练C")
    member, package_id = _member_with_package(
        client, admin_headers, gym_id, "13540000004", "课时会员", session_count=1
    )
    starts = datetime.now(timezone.utc) + timedelta(days=3)
    first = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "package_id": package_id,
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
        },
    )
    assert first.status_code == 200, first.text

    # 剩余 1 课时已被待上课程占满
    second = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "package_id": package_id,
            "starts_at": (starts + timedelta(days=1)).isoformat(),
            "ends_at": (starts + timedelta(days=1, hours=1)).isoformat(),
        },
    )
    assert second.status_code == 400
    assert second.json()["code"] == "no_sessions"

    by_coach = client.get(
        f"/api/v1/pt-appointments?merchant_id={gym_id}&coach_id={coach['id']}&status=booked",
        headers=admin_headers,
    )
    assert by_coach.status_code == 200, by_coach.text
    assert by_coach.json()["total"] == 1

    by_keyword = client.get(
        f"/api/v1/pt-appointments?merchant_id={gym_id}&q=课时会员",
        headers=admin_headers,
    )
    assert by_keyword.json()["total"] == 1

    miss = client.get(
        f"/api/v1/pt-appointments?merchant_id={gym_id}&q=不存在教练xyz",
        headers=admin_headers,
    )
    assert miss.json()["total"] == 0


def test_appointment_time_window_validation(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    coach = _coach(client, admin_headers, gym_id, "pt_coach_d", "预约教练D")
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13540000005", "name": "无课包会员", "merchant_id": gym_id},
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(days=1)

    reversed_time = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": (starts - timedelta(minutes=30)).isoformat(),
        },
    )
    assert reversed_time.status_code == 400
    assert reversed_time.json()["code"] == "invalid_time"

    too_long = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=9)).isoformat(),
        },
    )
    assert too_long.status_code == 400

    # 无课包也可排期（按教练课时费结算）
    ok = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
        },
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["package_id"] is None
