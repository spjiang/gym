"""收入构成拆分、活动看板与私教课时报表测试。"""

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _pay(client: TestClient, headers: dict, order_id: int) -> None:
    resp = client.post(
        f"/api/v1/orders/{order_id}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    assert resp.status_code == 200, resp.text


def test_revenue_split_by_business_line(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    today = date.today().isoformat()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13570000001", "name": "收入构成会员", "merchant_id": gym_id},
    ).json()

    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "构成门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "构成年卡",
            "product_type": "term",
            "price": "1200.00",
            "duration_days": 365,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    membership_order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    _pay(client, admin_headers, membership_order["id"])

    pt_product = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "构成私教10节",
            "price": "3000.00",
            "session_count": 10,
            "valid_days": 180,
            "all_coaches": True,
        },
    ).json()
    pt_order = client.post(
        "/api/v1/pt-packages/purchase",
        headers=admin_headers,
        json={"merchant_id": gym_id, "member_id": member["id"], "product_id": pt_product["id"]},
    ).json()
    _pay(client, admin_headers, pt_order["id"])

    starts = datetime.now(timezone.utc) + timedelta(days=2)
    activity = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "构成活动",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=2)).isoformat(),
            "capacity": 10,
            "price": "150.00",
        },
    ).json()
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)
    activity_reg = client.post(
        "/api/v1/activity-registrations",
        headers=admin_headers,
        json={"activity_id": activity["id"], "member_id": member["id"]},
    ).json()
    _pay(client, admin_headers, activity_reg["order"]["id"])

    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={"merchant_id": gym_id, "name": "构成蛋白粉", "price": "300.00", "unit": "罐"},
    ).json()
    client.post(
        f"/api/v1/retail/skus/{sku['id']}/stock/in",
        headers=admin_headers,
        json={"quantity": 5},
    )
    retail_order = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku["id"], "quantity": 1}],
        },
    ).json()
    _pay(client, admin_headers, retail_order["id"])

    resp = client.get(
        f"/api/v1/reports/revenue-split?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    rows = {row["category"]: row for row in body["rows"]}
    assert rows["membership"]["net_total"] == "1200.00"
    assert rows["pt"]["net_total"] == "3000.00"
    assert rows["activity"]["net_total"] == "150.00"
    assert rows["retail"]["net_total"] == "300.00"
    assert rows["group"]["net_total"] == "0.00"
    assert body["net_total"] == "4650.00"

    # 退款计入抵减
    refund = client.post(
        f"/api/v1/orders/{retail_order['id']}/refund",
        headers=admin_headers,
        json={"reason": "会员退货"},
    )
    assert refund.status_code == 200, refund.text
    after = client.get(
        f"/api/v1/reports/revenue-split?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    ).json()
    retail_row = next(r for r in after["rows"] if r["category"] == "retail")
    assert retail_row["refund_total"] == "300.00"
    assert retail_row["net_total"] == "0.00"
    assert after["net_total"] == "4350.00"


def test_activity_summary_report(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    starts = datetime.now(timezone.utc) + timedelta(hours=2)
    on_date = starts.date().isoformat()
    activity = client.post(
        "/api/v1/activities",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "看板活动",
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=2)).isoformat(),
            "capacity": 10,
            "price": "0",
        },
    ).json()
    client.post(f"/api/v1/activities/{activity['id']}/publish", headers=admin_headers)

    joined = []
    for idx in range(3):
        member = client.post(
            "/api/v1/members",
            headers=admin_headers,
            json={
                "phone": f"1357000100{idx}",
                "name": f"看板会员{idx}",
                "merchant_id": gym_id,
            },
        ).json()
        reg = client.post(
            "/api/v1/activity-registrations",
            headers=admin_headers,
            json={"activity_id": activity["id"], "member_id": member["id"]},
        ).json()["registration"]
        joined.append(reg)

    client.post(
        f"/api/v1/activity-registrations/{joined[0]['id']}/checkin", headers=admin_headers
    )
    client.post(
        f"/api/v1/activity-registrations/{joined[1]['id']}/cancel", headers=admin_headers
    )

    resp = client.get(
        f"/api/v1/reports/activity-summary?date_from={on_date}&date_to={on_date}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["activity_count"] == 1
    assert body["attended_count"] == 1
    assert body["cancelled_count"] == 1
    # 出席与待出席均计入报名口径
    assert body["registered_count"] == 2


def test_course_summary_includes_pt_appointments(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "report_pt_coach",
            "password": "Coach@123456",
            "display_name": "私教报表教练",
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
            "display_name": "私教报表教练",
            "hourly_rate": "300.00",
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13570002001", "name": "私教报表会员", "merchant_id": gym_id},
    ).json()

    starts = datetime.now(timezone.utc) + timedelta(hours=1)
    on_date = starts.date().isoformat()
    first = client.post(
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
    assert first.status_code == 200, first.text
    second = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach["id"],
            "starts_at": (starts + timedelta(hours=2)).isoformat(),
            "ends_at": (starts + timedelta(hours=3)).isoformat(),
        },
    )
    assert second.status_code == 200, second.text
    client.post(f"/api/v1/pt-appointments/{first.json()['id']}/complete", headers=admin_headers)

    resp = client.get(
        f"/api/v1/reports/course-summary?date_from={on_date}&date_to={on_date}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["pt_appointment_count"] == 2
    assert resp.json()["pt_completed_count"] == 1


def test_business_reports_require_permission(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "revenue_front",
            "password": "Front@123456",
            "display_name": "构成前台",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    )
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "revenue_front", "password": "Front@123456"},
    ).json()
    headers = {"Authorization": f"Bearer {login['access_token']}"}
    today = date.today().isoformat()
    for path in ("revenue-split", "activity-summary"):
        denied = client.get(
            f"/api/v1/reports/{path}?date_from={today}&date_to={today}",
            headers=headers,
        )
        assert denied.status_code == 403, denied.text
