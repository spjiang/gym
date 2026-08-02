"""经营报表汇总与权限测试。"""

from datetime import date, timedelta

from fastapi.testclient import TestClient


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_commerce_summary_and_csv(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    today = date.today().isoformat()

    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "title": "报表测收款",
            "amount": "100.00",
            "order_type": "retail",
        },
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    refunded = client.post(f"/api/v1/orders/{order['id']}/refund", headers=admin_headers)
    assert refunded.status_code == 200, refunded.text

    summary = client.get(
        f"/api/v1/reports/commerce-summary?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["charge_total"] == "100.00"
    assert body["refund_total"] == "100.00"
    assert body["net_total"] == "0.00"
    assert any(x["channel"] == "offline_cash" for x in body["by_channel"])
    assert any(x["order_type"] == "retail" for x in body["by_order_type"])

    csv_resp = client.get(
        f"/api/v1/reports/commerce-payments.csv?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert csv_resp.status_code == 200, csv_resp.text
    assert "text/csv" in csv_resp.headers.get("content-type", "")
    text = csv_resp.text
    assert "payment_id" in text
    assert "100.00" in text
    assert str(order["id"]) in text


def test_report_permission_and_merchant_isolation(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    gym_type = next(t for t in types if t["code"] == "gym")
    other = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"merchant_type_id": gym_type["id"], "name": "报表他店", "status": "active"},
    ).json()

    # 商户管理员仅本商户
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "report_admin",
            "password": "Report@123456",
            "display_name": "报表商管",
            "merchant_id": gym_id,
            "role_codes": ["merchant_admin"],
        },
    ).json()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "report_admin", "password": "Report@123456"},
    ).json()
    mheaders = {"Authorization": f"Bearer {login['access_token']}"}

    today = date.today().isoformat()
    ok = client.get(
        f"/api/v1/reports/commerce-summary?date_from={today}&date_to={today}",
        headers=mheaders,
    )
    assert ok.status_code == 200, ok.text
    assert ok.json()["merchant_id"] == gym_id

    cross = client.get(
        f"/api/v1/reports/commerce-summary?date_from={today}&date_to={today}&merchant_id={other['id']}",
        headers=mheaders,
    )
    assert cross.status_code == 403

    # 前台无 report:read
    client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "report_front",
            "password": "Front@123456",
            "display_name": "报表前台",
            "merchant_id": gym_id,
            "role_codes": ["front_desk"],
        },
    )
    flogin = client.post(
        "/api/v1/auth/login",
        json={"username": "report_front", "password": "Front@123456"},
    ).json()
    fheaders = {"Authorization": f"Bearer {flogin['access_token']}"}
    denied = client.get(
        f"/api/v1/reports/commerce-summary?date_from={today}&date_to={today}",
        headers=fheaders,
    )
    assert denied.status_code == 403

    # 无效区间
    bad = client.get(
        f"/api/v1/reports/commerce-summary?date_from={(date.today() + timedelta(days=1)).isoformat()}&date_to={today}",
        headers=admin_headers,
    )
    assert bad.status_code == 400

    assert staff["id"] > 0


def test_membership_course_inventory_summaries(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    today = date.today().isoformat()

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13650000001", "name": "报表会员", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "报表门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "报表月卡",
            "product_type": "term",
            "price": "199.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=admin_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text

    mem = client.get(
        f"/api/v1/reports/membership-summary?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert mem.status_code == 200, mem.text
    assert mem.json()["new_count"] >= 1
    assert mem.json()["active_count"] >= 1

    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "report_coach",
            "password": "Coach@123456",
            "display_name": "报表教练",
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
            "display_name": "报表教练",
        },
    ).json()
    course = client.post(
        "/api/v1/group-courses",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "报表团课",
            "default_capacity": 1,
            "default_duration_minutes": 60,
        },
    ).json()
    from datetime import datetime, timedelta, timezone

    start = datetime.now(timezone.utc) + timedelta(hours=2)
    end = start + timedelta(hours=1)
    session = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": start.isoformat(),
            "ends_at": end.isoformat(),
            "capacity": 1,
        },
    )
    assert session.status_code == 200, session.text
    booking = client.post(
        "/api/v1/group-bookings",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "session_id": session.json()["id"],
            "member_id": member["id"],
        },
    )
    assert booking.status_code == 200, booking.text
    checkin = client.post(
        f"/api/v1/group-bookings/{booking.json()['id']}/checkin",
        headers=admin_headers,
        json={"status": "attended"},
    )
    assert checkin.status_code == 200, checkin.text

    course_sum = client.get(
        f"/api/v1/reports/course-summary?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert course_sum.status_code == 200, course_sum.text
    assert course_sum.json()["session_count"] >= 1
    assert course_sum.json()["booking_count"] >= 1
    assert course_sum.json()["full_session_count"] >= 1
    assert course_sum.json()["attended_count"] >= 1

    sku = client.post(
        "/api/v1/retail/skus",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "报表水",
            "price": "5.00",
            "unit": "瓶",
            "low_stock_threshold": 10,
        },
    ).json()
    client.post(
        f"/api/v1/retail/skus/{sku['id']}/stock/in",
        headers=admin_headers,
        json={"quantity": 3},
    )
    retail = client.post(
        "/api/v1/retail/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "items": [{"sku_id": sku["id"], "quantity": 2}],
        },
    ).json()
    client.post(
        f"/api/v1/orders/{retail['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )

    inv = client.get(
        f"/api/v1/reports/inventory-summary?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert inv.status_code == 200, inv.text
    assert inv.json()["sale_qty"] >= 2
    row = next(s for s in inv.json()["skus"] if s["sku_id"] == sku["id"])
    assert row["stock_qty"] == 1
    assert row["is_low"] is True
