"""分成规则、自动计提与结算流转测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import new_coach_member


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _staff_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/auth/me", headers=headers).json()["id"]


def _ensure_sales_rep(client: TestClient, headers: dict, gym_id: int) -> dict:
    """开单员工须先有销售档案，销售提成才记到绑定会员。"""
    staff_id = _staff_id(client, headers)
    listed = client.get(
        f"/api/v1/sales-reps?merchant_id={gym_id}&page_size=100",
        headers=headers,
    )
    assert listed.status_code == 200, listed.text
    for item in listed.json()["items"]:
        if item["staff_user_id"] == staff_id and item["is_active"]:
            return item
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={
            "phone": f"1355999{staff_id:04d}",
            "name": "销售绑定会员",
            "merchant_id": gym_id,
        },
    ).json()
    created = client.post(
        "/api/v1/sales-reps",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff_id,
            "member_id": member["id"],
            "display_name": "测试销售",
        },
    )
    assert created.status_code == 200, created.text
    return created.json()


def _rule(client: TestClient, headers: dict, gym_id: int, **overrides) -> dict:
    payload = {
        "merchant_id": gym_id,
        "name": "会籍销售提成",
        "scope": "membership_sale",
        "beneficiary": "seller",
        "basis": "percent",
        "rate": "0.1",
    }
    payload.update(overrides)
    resp = client.post("/api/v1/commission-rules", headers=headers, json=payload)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _sell_membership(
    client: TestClient, headers: dict, gym_id: int, *, phone: str, price: str = "1000.00"
) -> dict:
    _ensure_sales_rep(client, headers, gym_id)
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": f"提成门{phone[-4:]}", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "name": f"提成年卡{phone[-4:]}",
            "product_type": "term",
            "price": price,
            "duration_days": 365,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": phone, "name": f"提成会员{phone[-4:]}", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    return {"member": member, "order": order}


def test_rule_validation(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)

    wrong_beneficiary = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "受益方错配",
            "scope": "group_session",
            "beneficiary": "referrer",
            "basis": "per_head",
            "unit_amount": "10.00",
        },
    )
    assert wrong_beneficiary.status_code == 400
    assert wrong_beneficiary.json()["code"] == "invalid_beneficiary"

    referral_seller = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "推荐场景错配销售",
            "scope": "referral",
            "beneficiary": "seller",
            "basis": "fixed",
            "unit_amount": "10.00",
        },
    )
    assert referral_seller.status_code == 400
    assert referral_seller.json()["code"] == "invalid_beneficiary"

    coach_on_sale = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "销售给教练",
            "scope": "membership_sale",
            "beneficiary": "coach",
            "basis": "percent",
            "rate": "0.1",
        },
    )
    assert coach_on_sale.status_code == 200, coach_on_sale.text

    rate_over = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "比例超限",
            "scope": "membership_sale",
            "beneficiary": "seller",
            "basis": "percent",
            "rate": "1.5",
        },
    )
    assert rate_over.status_code == 400
    assert rate_over.json()["code"] == "invalid_rate"

    group_percent = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "团课按比例",
            "scope": "group_session",
            "beneficiary": "coach",
            "basis": "percent",
            "rate": "0.2",
        },
    )
    assert group_percent.status_code == 400
    assert group_percent.json()["code"] == "invalid_basis"

    missing_unit = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "缺少单价",
            "scope": "group_session",
            "beneficiary": "coach",
            "basis": "per_head",
        },
    )
    assert missing_unit.status_code == 400
    assert missing_unit.json()["code"] == "invalid_unit_amount"

    now = datetime.now(timezone.utc)
    bad_range = client.post(
        "/api/v1/commission-rules",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "生效区间错误",
            "scope": "retail_sale",
            "beneficiary": "seller",
            "basis": "fixed",
            "unit_amount": "5.00",
            "effective_from": now.isoformat(),
            "effective_to": (now - timedelta(days=1)).isoformat(),
        },
    )
    assert bad_range.status_code == 400
    assert bad_range.json()["code"] == "invalid_time"


def test_membership_sale_accrual_and_settlement(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    rule = _rule(client, admin_headers, gym_id, max_amount="80.00")
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000001")

    records = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    )
    assert records.status_code == 200, records.text
    assert records.json()["total"] == 1
    record = records.json()["items"][0]
    assert record["rule_id"] == rule["id"]
    assert record["rule_name"] == "会籍销售提成"
    assert record["order_id"] == sold["order"]["id"]
    assert record["base_amount"] == "1000.00"
    # 10% = 100，被上限 80 截断
    assert record["amount"] == "80.00"
    assert record["status"] == "pending"
    assert record["beneficiary_type"] == "member"

    bad_jump = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert bad_jump.status_code == 400
    assert bad_jump.json()["code"] == "invalid_state"

    confirmed = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"

    settled = client.post(
        "/api/v1/commission-records/batch-status",
        headers=admin_headers,
        json={"ids": [record["id"], 999999], "status": "paid"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json() == {"updated": 1, "skipped": 1}

    after = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}",
        headers=admin_headers,
    ).json()["items"][0]
    assert after["status"] == "paid"
    assert after["settled_at"]

    frozen = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    assert frozen.status_code == 400

    today = datetime.now(timezone.utc).date().isoformat()
    summary = client.get(
        f"/api/v1/commission-summary?date_from={today}&date_to={today}&merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert summary.status_code == 200, summary.text
    body = summary.json()
    assert body["total_amount"] == "80.00"
    assert body["paid_amount"] == "80.00"
    assert any(row["scope"] == "membership_sale" for row in body["by_scope"])
    assert body["sellers"]
    assert body["sellers"][0]["sales_amount"] == "1000.00"
    assert body["sellers"][0]["commission_amount"] == "80.00"


def test_rule_min_base_and_deactivate_instead_of_delete(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    high_bar = _rule(
        client,
        admin_headers,
        gym_id,
        name="高门槛提成",
        min_base_amount="5000.00",
    )
    _sell_membership(client, admin_headers, gym_id, phone="13550000002", price="1000.00")
    empty = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}",
        headers=admin_headers,
    )
    assert empty.json()["total"] == 0

    deleted = client.delete(f"/api/v1/commission-rules/{high_bar['id']}", headers=admin_headers)
    assert deleted.status_code == 200, deleted.text
    assert deleted.json() == {"ok": True, "deactivated": False}

    used = _rule(client, admin_headers, gym_id, name="使用中提成")
    _sell_membership(client, admin_headers, gym_id, phone="13550000003")
    assert (
        client.get(
            f"/api/v1/commission-records?merchant_id={gym_id}", headers=admin_headers
        ).json()["total"]
        == 1
    )
    soft = client.delete(f"/api/v1/commission-rules/{used['id']}", headers=admin_headers)
    assert soft.status_code == 200, soft.text
    assert soft.json() == {"ok": True, "deactivated": True}
    still_there = client.get(
        f"/api/v1/commission-rules?merchant_id={gym_id}&is_active=false",
        headers=admin_headers,
    )
    assert any(r["id"] == used["id"] for r in still_there.json()["items"])


def test_no_sales_rep_skips_sale_commission(client: TestClient, admin_headers: dict):
    """未建销售档案时，开单不产生销售提成。"""
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "no_sales_rep",
            "password": "Staff@123456",
            "display_name": "无档案销售",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    ).json()
    login = client.post(
        "/api/v1/auth/login",
        json={"username": "no_sales_rep", "password": "Staff@123456"},
    )
    assert login.status_code == 200, login.text
    staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "无销售门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "无销售年卡",
            "product_type": "term",
            "price": "1000.00",
            "duration_days": 365,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13550000099", "name": "无销售会员", "merchant_id": gym_id},
    ).json()
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=staff_headers,
        json={"member_id": member["id"], "product_id": product["id"], "merchant_id": gym_id},
    ).json()
    paid = client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=staff_headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    records = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()
    assert records["total"] == 0


def test_sales_rep_crud(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "sales_rep_user",
            "password": "Staff@123456",
            "display_name": "销售小王",
            "merchant_id": gym_id,
            "role_codes": ["gym_ops"],
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13550001111", "name": "销售会员小王", "merchant_id": gym_id},
    ).json()
    created = client.post(
        "/api/v1/sales-reps",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": member["id"],
            "display_name": "销售小王",
        },
    )
    assert created.status_code == 200, created.text
    rep_id = created.json()["id"]
    assert created.json()["member_phone"] == "13550001111"

    dup_staff = client.post(
        "/api/v1/sales-reps",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": member["id"],
            "display_name": "重复",
        },
    )
    assert dup_staff.status_code == 400
    assert dup_staff.json()["code"] == "staff_in_use"

    other_member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13550001112", "name": "销售会员小李", "merchant_id": gym_id},
    ).json()
    updated = client.patch(
        f"/api/v1/sales-reps/{rep_id}",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff["id"],
            "member_id": other_member["id"],
            "display_name": "销售小王（换绑）",
        },
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["member_id"] == other_member["id"]

    deactivated = client.post(
        f"/api/v1/sales-reps/{rep_id}/deactivate",
        headers=admin_headers,
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False

    all_reps = client.get("/api/v1/sales-reps", headers=admin_headers)
    assert all_reps.status_code == 200, all_reps.text
    assert all_reps.json()["total"] >= 1


def test_refund_voids_commission(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000004")
    order_id = sold["order"]["id"]

    refund = client.post(
        f"/api/v1/orders/{order_id}/refund",
        headers=admin_headers,
        json={"reason": "会员反悔"},
    )
    assert refund.status_code == 200, refund.text

    records = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}",
        headers=admin_headers,
    ).json()["items"]
    assert records
    assert records[0]["status"] == "void"


def test_member_referral_first_order_only_credits_rebate(client: TestClient, admin_headers: dict):
    """会员推荐收益进返点账户，首单规则同样生效。"""
    gym_id = _gym_id(client, admin_headers)
    _rule(
        client,
        admin_headers,
        gym_id,
        name="推荐提成",
        scope="referral",
        beneficiary="referrer",
        basis="fixed",
        unit_amount="50.00",
        first_order_only=True,
    )
    referrer = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13550001001", "name": "推荐人", "merchant_id": gym_id},
    ).json()

    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "推荐门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "推荐月卡",
            "product_type": "term",
            "price": "500.00",
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    ).json()
    invited = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={
            "phone": "13550001002",
            "name": "被推荐人",
            "merchant_id": gym_id,
            "referrer_member_id": referrer["id"],
        },
    )
    assert invited.status_code == 200, invited.text
    assert invited.json()["referrer_member_id"] == referrer["id"]
    assert "推荐人" in invited.json()["referrer_display"]
    invited_id = invited.json()["id"]

    for _ in range(2):
        order = client.post(
            "/api/v1/memberships/purchase",
            headers=admin_headers,
            json={"member_id": invited_id, "product_id": product["id"], "merchant_id": gym_id},
        ).json()
        client.post(
            f"/api/v1/orders/{order['id']}/pay/offline",
            headers=admin_headers,
            json={"channel": "offline_cash"},
        )

    # 会员推荐不再写提成记录
    referral_records = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=referral",
        headers=admin_headers,
    ).json()
    assert referral_records["total"] == 0

    ledgers = client.get(
        f"/api/v1/rebate-ledgers?member_id={referrer['id']}",
        headers=admin_headers,
    )
    assert ledgers.status_code == 200, ledgers.text
    # 仅首单入账
    assert ledgers.json()["total"] == 1
    row = ledgers.json()["items"][0]
    assert row["kind"] == "earn"
    assert row["amount"] == "50.00"
    assert row["balance_after"] == "50.00"
    assert row["from_member_id"] == invited_id

    promotion = client.get(
        f"/api/v1/members/{referrer['id']}/promotion", headers=admin_headers
    ).json()
    assert promotion["account"]["balance"] == "50.00"
    assert promotion["account"]["total_earned"] == "50.00"
    assert promotion["downline_count"] == 1

    referrer_view = client.get(
        f"/api/v1/members?referrer_member_id={referrer['id']}",
        headers=admin_headers,
    )
    assert referrer_view.status_code == 200, referrer_view.text
    assert [m["id"] for m in referrer_view.json()["items"]] == [invited_id]
    detail = client.get(f"/api/v1/members?q=13550001001", headers=admin_headers).json()["items"][0]
    assert detail["referred_count"] == 1


def test_group_session_commission_follows_checkin(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(
        client,
        admin_headers,
        gym_id,
        name="团课人头提成",
        scope="group_session",
        beneficiary="coach",
        basis="per_head",
        unit_amount="15.00",
    )
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "group_commission_coach",
            "password": "Coach@123456",
            "display_name": "团课提成教练",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    ).json()
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={"merchant_id": gym_id, "staff_user_id": staff["id"], "member_id": new_coach_member(client, admin_headers, gym_id)["id"], "display_name": "团课提成教练"},
    ).json()
    course = client.post(
        "/api/v1/group-courses",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "提成团课",
            "default_capacity": 5,
            "book_ahead_minutes": 0,
            "cancel_ahead_minutes": 0,
        },
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(minutes=20)
    session = client.post(
        "/api/v1/group-sessions",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "course_id": course["id"],
            "coach_id": coach["id"],
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
            "capacity": 5,
        },
    )
    assert session.status_code == 200, session.text

    bookings = []
    for idx in range(2):
        member = client.post(
            "/api/v1/members",
            headers=admin_headers,
            json={
                "phone": f"1355000300{idx}",
                "name": f"团课会员{idx}",
                "merchant_id": gym_id,
            },
        ).json()
        _sell_membership_to(client, admin_headers, gym_id, member["id"], suffix=str(idx))
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
        bookings.append(booking.json())

    for booking in bookings:
        checked = client.post(
            f"/api/v1/group-bookings/{booking['id']}/checkin",
            headers=admin_headers,
            json={"status": "attended"},
        )
        assert checked.status_code == 200, checked.text

    rows = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=group_session",
        headers=admin_headers,
    ).json()["items"]
    # 同场次只保留一条记录，金额随出席人数重算
    assert len(rows) == 1
    assert rows[0]["quantity"] == 2
    assert rows[0]["amount"] == "30.00"
    assert rows[0]["beneficiary_type"] == "member"
    assert rows[0]["category"] == "session"
    assert rows[0]["coach_id"] == coach["id"]
    assert rows[0]["source_type"] == "group_session"
    assert rows[0]["source_id"] == session.json()["id"]
    assert "团课提成教练" in rows[0]["note"]

    revised = client.post(
        f"/api/v1/group-bookings/{bookings[0]['id']}/checkin",
        headers=admin_headers,
        json={"status": "no_show"},
    )
    assert revised.status_code == 200, revised.text
    after = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=group_session",
        headers=admin_headers,
    ).json()["items"]
    assert len(after) == 1
    assert after[0]["quantity"] == 1
    assert after[0]["amount"] == "15.00"


def _sell_membership_to(
    client: TestClient, headers: dict, gym_id: int, member_id: int, *, suffix: str
) -> None:
    """给会员办一张期限卡，满足团课预约的会籍校验。"""
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": f"团课门{suffix}", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "name": f"团课月卡{suffix}",
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


def test_pt_session_commission_on_complete(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(
        client,
        admin_headers,
        gym_id,
        name="私教课时提成",
        scope="pt_session",
        beneficiary="coach",
        basis="per_session",
        unit_amount="60.00",
    )
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "commission_coach",
            "password": "Coach@123456",
            "display_name": "提成教练",
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
            "display_name": "提成教练",
            "hourly_rate": "400.00",
        },
    ).json()
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13550002001", "name": "私教提成会员", "merchant_id": gym_id},
    ).json()
    starts = datetime.now(timezone.utc) + timedelta(days=1)
    appointment = client.post(
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
    assert appointment.status_code == 200, appointment.text
    done = client.post(
        f"/api/v1/pt-appointments/{appointment.json()['id']}/complete",
        headers=admin_headers,
    )
    assert done.status_code == 200, done.text

    rows = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=pt_session",
        headers=admin_headers,
    ).json()["items"]
    assert len(rows) == 1
    assert rows[0]["amount"] == "60.00"
    assert rows[0]["beneficiary_type"] == "member"
    assert rows[0]["category"] == "session"
    assert rows[0]["coach_id"] == coach["id"]
    assert rows[0]["source_type"] == "pt_appointment"
    assert "提成教练" in rows[0]["note"]
    assert rows[0]["source_type"] == "pt_appointment"


def _sales_payout_beneficiary(client: TestClient, headers: dict, gym_id: int) -> dict:
    rep = _ensure_sales_rep(client, headers, gym_id)
    return {"beneficiary_type": "member", "beneficiary_id": rep["member_id"]}


def test_partial_refund_scales_open_commission_payout(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000031")
    order_id = sold["order"]["id"]
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    assert record["amount"] == "100.00"
    confirmed = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200, confirmed.text

    payout = client.post(
        "/api/v1/payouts",
        headers=admin_headers,
        json={
            "source": "commission",
            **_sales_payout_beneficiary(client, admin_headers, gym_id),
            "merchant_id": gym_id,
            "record_ids": [record["id"]],
        },
    )
    assert payout.status_code == 200, payout.text
    assert payout.json()["amount"] == "100.00"
    assert payout.json()["status"] == "requested"
    payout_id = payout.json()["id"]

    refunded = client.post(
        f"/api/v1/orders/{order_id}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "amount": "100.00", "reason": "部分退同步提现", "force": True},
    )
    assert refunded.status_code == 200, refunded.text

    listed = client.get("/api/v1/payouts", headers=admin_headers, params={"status": "requested"}).json()
    hit = next(x for x in listed["items"] if x["id"] == payout_id)
    assert hit["amount"] == "90.00"
    assert hit["status"] == "requested"


def test_full_refund_rejects_open_commission_payout(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000032")
    order_id = sold["order"]["id"]
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    payout = client.post(
        "/api/v1/payouts",
        headers=admin_headers,
        json={
            "source": "commission",
            **_sales_payout_beneficiary(client, admin_headers, gym_id),
            "merchant_id": gym_id,
            "record_ids": [record["id"]],
        },
    )
    assert payout.status_code == 200, payout.text
    payout_id = payout.json()["id"]

    refunded = client.post(
        f"/api/v1/orders/{order_id}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "全额退驳回提现"},
    )
    assert refunded.status_code == 200, refunded.text

    listed = client.get("/api/v1/payouts", headers=admin_headers).json()["items"]
    hit = next(x for x in listed if x["id"] == payout_id)
    assert hit["status"] == "rejected"


def test_commission_settings_hold_days_block_settlement(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    saved = client.put(
        "/api/v1/site/commission-settings",
        headers=admin_headers,
        json={"settle_hold_days": 7, "remark": "测试冷却"},
    )
    assert saved.status_code == 200, saved.text
    assert saved.json()["settle_hold_days"] == 7
    got = client.get("/api/v1/site/commission-settings", headers=admin_headers)
    assert got.status_code == 200, got.text
    assert got.json()["settle_hold_days"] == 7

    _rule(client, admin_headers, gym_id)
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000041")
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    assert record["settle_ready"] is False
    assert record["settle_hold_until"]

    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    blocked = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert blocked.status_code == 400, blocked.text
    assert blocked.json()["code"] == "commission_hold"

    batch = client.post(
        "/api/v1/commission-records/batch-status",
        headers=admin_headers,
        json={"ids": [record["id"]], "status": "paid"},
    )
    assert batch.status_code == 200, batch.text
    assert batch.json() == {"updated": 0, "skipped": 1}

    client.put(
        "/api/v1/site/commission-settings",
        headers=admin_headers,
        json={"settle_hold_days": 0},
    )
    settled = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert settled.status_code == 200, settled.text
    assert settled.json()["status"] == "paid"
    assert sold["order"]["id"]


def test_paid_refund_creates_debt_and_next_settlement_offsets(
    client: TestClient, admin_headers: dict
):
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    first = _sell_membership(client, admin_headers, gym_id, phone="13550000042")
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    paid = client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert paid.status_code == 200, paid.text

    refunded = client.post(
        f"/api/v1/orders/{first['order']['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "已打款后退款记欠额", "force": True},
    )
    assert refunded.status_code == 200, refunded.text

    listed = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}",
        headers=admin_headers,
    ).json()["items"]
    hit = next(x for x in listed if x["id"] == record["id"])
    assert hit["status"] == "paid"

    debts = client.get("/api/v1/commission-debts", headers=admin_headers)
    assert debts.status_code == 200, debts.text
    assert debts.json()
    assert debts.json()[0]["debt_amount"] == "100.00"
    beneficiary_id = debts.json()[0]["beneficiary_id"]
    beneficiary_type = debts.json()[0]["beneficiary_type"]

    recovered = client.post(
        "/api/v1/commission-debts/recover",
        headers=admin_headers,
        json={
            "beneficiary_type": beneficiary_type,
            "beneficiary_id": beneficiary_id,
            "amount": "20.00",
            "note": "现金追回",
        },
    )
    assert recovered.status_code == 200, recovered.text
    assert recovered.json()["debt_amount"] == "80.00"

    _sell_membership(client, admin_headers, gym_id, phone="13550000043")
    rows = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale&status=pending",
        headers=admin_headers,
    ).json()["items"]
    second = rows[0]
    client.post(
        f"/api/v1/commission-records/{second['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    settled = client.post(
        f"/api/v1/commission-records/{second['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    assert settled.status_code == 200, settled.text
    assert "抵扣欠额" in (settled.json().get("note") or "")

    leftover = client.get("/api/v1/commission-debts", headers=admin_headers).json()
    assert leftover == []


def test_payout_offsets_commission_debt(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    first = _sell_membership(client, admin_headers, gym_id, phone="13550000044")
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    refunded = client.post(
        f"/api/v1/orders/{first['order']['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "已打款后退款", "force": True},
    )
    assert refunded.status_code == 200, refunded.text

    _sell_membership(client, admin_headers, gym_id, phone="13550000045")
    second = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale&status=pending",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{second['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    payout = client.post(
        "/api/v1/payouts",
        headers=admin_headers,
        json={
            "source": "commission",
            **_sales_payout_beneficiary(client, admin_headers, gym_id),
            "merchant_id": gym_id,
            "record_ids": [second["id"]],
        },
    )
    assert payout.status_code == 200, payout.text
    body = payout.json()
    assert body["offset_amount"] == "100.00"
    assert body["amount"] == "0.00"
    assert body["status"] == "paid"
    leftover = client.get("/api/v1/commission-debts", headers=admin_headers).json()
    assert leftover == []


def test_partial_refund_syncs_payout_offset_amount(client: TestClient, admin_headers: dict):
    """退款同步未打款提现单时，须重算欠额抵扣与现金金额。"""
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    first = _sell_membership(client, admin_headers, gym_id, phone="13550000046")
    record1 = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record1['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    client.post(
        f"/api/v1/commission-records/{record1['id']}/status",
        headers=admin_headers,
        json={"status": "paid"},
    )
    refunded = client.post(
        f"/api/v1/orders/{first['order']['id']}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "reason": "制造欠额", "force": True},
    )
    assert refunded.status_code == 200, refunded.text

    debts = client.get("/api/v1/commission-debts", headers=admin_headers).json()
    client.post(
        "/api/v1/commission-debts/recover",
        headers=admin_headers,
        json={
            "beneficiary_type": debts[0]["beneficiary_type"],
            "beneficiary_id": debts[0]["beneficiary_id"],
            "amount": "60.00",
            "note": "部分追回",
        },
    )

    _sell_membership(client, admin_headers, gym_id, phone="13550000047")
    record2 = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale&status=pending",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record2['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    open_payout = client.post(
        "/api/v1/payouts",
        headers=admin_headers,
        json={
            "source": "commission",
            **_sales_payout_beneficiary(client, admin_headers, gym_id),
            "merchant_id": gym_id,
            "record_ids": [record2["id"]],
        },
    )
    assert open_payout.status_code == 200, open_payout.text
    payout_body = open_payout.json()
    assert payout_body["offset_amount"] == "40.00"
    assert payout_body["amount"] == "60.00"
    assert payout_body["status"] == "requested"
    payout_id = payout_body["id"]
    order2_id = record2["order_id"]

    partial = client.post(
        f"/api/v1/orders/{order2_id}/refund",
        headers=admin_headers,
        json={"channel": "offline_cash", "amount": "500.00", "reason": "部分退同步 offset", "force": True},
    )
    assert partial.status_code == 200, partial.text

    listed = client.get("/api/v1/payouts", headers=admin_headers).json()["items"]
    hit = next(x for x in listed if x["id"] == payout_id)
    assert hit["offset_amount"] == "40.00"
    assert hit["amount"] == "10.00"
    assert hit["status"] == "requested"


def test_batch_paid_skips_locked_commission_record(client: TestClient, admin_headers: dict):
    """批量结算应跳过已被未完结提现单锁定的提成记录。"""
    gym_id = _gym_id(client, admin_headers)
    _rule(client, admin_headers, gym_id)
    sold = _sell_membership(client, admin_headers, gym_id, phone="13550000049")
    record = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    client.post(
        f"/api/v1/commission-records/{record['id']}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    payout = client.post(
        "/api/v1/payouts",
        headers=admin_headers,
        json={
            "source": "commission",
            **_sales_payout_beneficiary(client, admin_headers, gym_id),
            "merchant_id": gym_id,
            "record_ids": [record["id"]],
        },
    )
    assert payout.status_code == 200, payout.text
    assert payout.json()["status"] == "requested"

    batch = client.post(
        "/api/v1/commission-records/batch-status",
        headers=admin_headers,
        json={"ids": [record["id"]], "status": "paid"},
    )
    assert batch.status_code == 200, batch.text
    assert batch.json() == {"updated": 0, "skipped": 1}

    still = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=membership_sale",
        headers=admin_headers,
    ).json()["items"][0]
    assert still["status"] == "confirmed"
    assert sold["order"]["id"]

