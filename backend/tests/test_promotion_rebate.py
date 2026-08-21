"""统一推广方案：下级折扣、返点入账冲回、会员提现与教练佣金提现测试。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from tests.conftest import new_coach_member

from app.core.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member(client: TestClient, headers: dict, gym_id: int, phone: str, name: str) -> dict:
    created = client.post(
        "/api/v1/members",
        headers=headers,
        json={"phone": phone, "name": name, "merchant_id": gym_id},
    )
    assert created.status_code == 200, created.text
    return created.json()


def _member_headers(client: TestClient, phone: str, gym_id: int, code: str | None = None) -> dict:
    payload: dict = {"phone": phone, "merchant_id": gym_id}
    assert client.post("/api/v1/member/auth/otp/send", json=payload).status_code == 200
    verify_payload = {**payload, "code": get_settings().member_otp_mock_code}
    if code is not None:
        verify_payload["referral_code"] = code
    verify = client.post("/api/v1/member/auth/otp/verify", json=verify_payload)
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def _my_code(client: TestClient, headers: dict, member_id: int) -> str:
    resp = client.get(f"/api/v1/members/{member_id}/promotion", headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()["code"]


def _membership_product(
    client: TestClient, headers: dict, gym_id: int, name: str, price: str
) -> dict:
    point = client.post(
        "/api/v1/access-points",
        headers=headers,
        json={"name": f"{name}门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=headers,
        json={
            "merchant_id": gym_id,
            "name": name,
            "product_type": "term",
            "price": price,
            "duration_days": 30,
            "access_point_ids": [point["id"]],
            "is_active": True,
        },
    )
    assert product.status_code == 200, product.text
    return product.json()


def _purchase_and_pay(
    client: TestClient, headers: dict, gym_id: int, member_id: int, product_id: int
) -> dict:
    order = client.post(
        "/api/v1/memberships/purchase",
        headers=headers,
        json={"member_id": member_id, "product_id": product_id, "merchant_id": gym_id},
    )
    assert order.status_code == 200, order.text
    paid = client.post(
        f"/api/v1/orders/{order.json()['id']}/pay/offline",
        headers=headers,
        json={"channel": "offline_cash"},
    )
    assert paid.status_code == 200, paid.text
    return paid.json()


def test_site_default_discount_and_rebate_accrual_and_reversal(
    client: TestClient, admin_headers: dict
):
    """场地默认比例生效：下级享 9 折，上级按实付返 5%，退款按比例冲回。"""
    gym_id = _gym_id(client, admin_headers)
    settings = client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={
            "default_rebate_rate": "0.05",
            "default_downline_discount_rate": "0.10",
            "min_withdraw_amount": "1.00",
        },
    )
    assert settings.status_code == 200, settings.text
    assert settings.json()["configured"] is True
    assert settings.json()["default_rebate_rate"] == "0.0500"

    upline = _member(client, admin_headers, gym_id, "13570000001", "上级会员")
    code = _my_code(client, admin_headers, upline["id"])
    _member_headers(client, "13570000002", gym_id, code)
    downline = client.get("/api/v1/members?q=13570000002", headers=admin_headers).json()["items"][0]
    assert downline["referrer_member_id"] == upline["id"]

    listing = client.get(
        "/api/v1/member-promotions",
        headers=admin_headers,
        params={"q": "上级会员", "has_downline": True},
    )
    assert listing.status_code == 200, listing.text
    listed = next(row for row in listing.json()["items"] if row["member_id"] == upline["id"])
    assert listed["code"] == code
    assert listed["downline_count"] >= 1

    product = _membership_product(client, admin_headers, gym_id, "折扣月卡", "1000.00")
    order = _purchase_and_pay(client, admin_headers, gym_id, downline["id"], product["id"])
    assert order["original_amount"] == "1000.00"
    assert order["promotion_discount_amount"] == "100.00"
    assert order["amount"] == "900.00"
    assert order["promoter_code"] == code

    promotion = client.get(
        f"/api/v1/members/{upline['id']}/promotion", headers=admin_headers
    ).json()
    # 45.00 = 实付 900 × 5%
    assert promotion["account"]["balance"] == "45.00"
    assert promotion["account"]["total_earned"] == "45.00"

    refund = client.post(
        f"/api/v1/orders/{order['id']}/refund",
        headers=admin_headers,
        json={"reason": "会员反悔"},
    )
    assert refund.status_code == 200, refund.text

    ledgers = client.get(
        f"/api/v1/rebate-ledgers?member_id={upline['id']}", headers=admin_headers
    ).json()["items"]
    assert [(row["kind"], row["amount"]) for row in ledgers] == [
        ("reverse", "-45.00"),
        ("earn", "45.00"),
    ]
    after = client.get(f"/api/v1/members/{upline['id']}/promotion", headers=admin_headers).json()
    assert after["account"]["balance"] == "0.00"
    assert after["account"]["debt_amount"] == "0.00"


def test_admin_open_promotion_issues_code_for_legacy_member(
    client: TestClient, admin_headers: dict
):
    """历史会员无推广位时，运营打开推广详情即补发卡和链接。"""
    gym_id = _gym_id(client, admin_headers)
    client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={"auto_create_member_code": False},
    )
    member = _member(client, admin_headers, gym_id, "13570002001", "历史会员")
    listed = client.get(
        "/api/v1/member-promotions",
        headers=admin_headers,
        params={"q": "13570002001"},
    ).json()["items"][0]
    assert listed["code"] is None
    assert listed["link"] is None

    opened = client.get(f"/api/v1/members/{member['id']}/promotion", headers=admin_headers)
    assert opened.status_code == 200, opened.text
    body = opened.json()
    assert body["code"]
    assert body["link"]
    assert body["is_active"] is True
    assert "promoter=" in body["link"]


def test_member_override_takes_priority_over_site_default(
    client: TestClient, admin_headers: dict
):
    """会员个性化比例优先于场地默认，且折扣为 0 时按原价成交。"""
    gym_id = _gym_id(client, admin_headers)
    client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={"default_rebate_rate": "0.05", "default_downline_discount_rate": "0.10"},
    )
    upline = _member(client, admin_headers, gym_id, "13570001001", "定制上级")
    configured = client.patch(
        f"/api/v1/members/{upline['id']}/promotion",
        headers=admin_headers,
        json={"rebate_rate": "0.2", "downline_discount_rate": "0"},
    )
    assert configured.status_code == 200, configured.text
    assert configured.json()["rebate_rate"] == "0.2000"
    assert configured.json()["downline_discount_rate"] == "0.0000"
    code = configured.json()["code"]

    _member_headers(client, "13570001002", gym_id, code)
    downline = client.get("/api/v1/members?q=13570001002", headers=admin_headers).json()["items"][0]
    product = _membership_product(client, admin_headers, gym_id, "定制月卡", "500.00")
    order = _purchase_and_pay(client, admin_headers, gym_id, downline["id"], product["id"])
    assert order["promotion_discount_amount"] == "0.00"
    assert order["amount"] == "500.00"

    promotion = client.get(
        f"/api/v1/members/{upline['id']}/promotion", headers=admin_headers
    ).json()
    assert promotion["account"]["balance"] == "100.00"

    too_high = client.patch(
        f"/api/v1/members/{upline['id']}/promotion",
        headers=admin_headers,
        json={"downline_discount_rate": "0.95"},
    )
    assert too_high.status_code == 400
    assert too_high.json()["code"] == "invalid_rate"


def test_member_rebate_withdraw_lifecycle(client: TestClient, admin_headers: dict):
    """会员端提现：余额校验 → 冻结 → 驳回解冻 → 重新申请 → 线下打款登记。"""
    gym_id = _gym_id(client, admin_headers)
    client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={"min_withdraw_amount": "10.00"},
    )
    member = _member(client, admin_headers, gym_id, "13570002001", "提现会员")
    mheaders = _member_headers(client, "13570002001", gym_id)

    mine = client.get("/api/v1/member/promotion", headers=mheaders)
    assert mine.status_code == 200, mine.text
    assert mine.json()["code"]
    assert mine.json()["link"].endswith(mine.json()["code"])
    assert mine.json()["balance"] == "0.00"
    assert mine.json()["min_withdraw_amount"] == "10.00"

    empty = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "20.00"}
    )
    assert empty.status_code == 400
    assert empty.json()["code"] == "insufficient_balance"

    adjusted = client.post(
        f"/api/v1/members/{member['id']}/rebate-adjust",
        headers=admin_headers,
        json={"amount": "80.00", "note": "线下活动补发"},
    )
    assert adjusted.status_code == 200, adjusted.text
    assert adjusted.json()["balance"] == "80.00"

    too_small = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "5.00"}
    )
    assert too_small.status_code == 400
    assert too_small.json()["code"] == "amount_too_small"

    requested = client.post(
        "/api/v1/member/promotion/withdrawals",
        headers=mheaders,
        json={"amount": "50.00", "note": "微信收款"},
    )
    assert requested.status_code == 200, requested.text
    payout_id = requested.json()["id"]
    assert requested.json()["status"] == "requested"

    again = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "10.00"}
    )
    assert again.status_code == 400
    assert again.json()["code"] == "payout_in_progress"

    frozen = client.get("/api/v1/member/promotion", headers=mheaders).json()
    assert frozen["balance"] == "30.00"
    assert frozen["frozen_amount"] == "50.00"

    rejected = client.post(
        f"/api/v1/payouts/{payout_id}/reject",
        headers=admin_headers,
        json={"reason": "收款信息不符"},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    reverted = client.get("/api/v1/member/promotion", headers=mheaders).json()
    assert reverted["balance"] == "80.00"
    assert reverted["frozen_amount"] == "0.00"

    retry = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "80.00"}
    ).json()
    approved = client.post(f"/api/v1/payouts/{retry['id']}/approve", headers=admin_headers)
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"

    paid = client.post(
        f"/api/v1/payouts/{retry['id']}/pay",
        headers=admin_headers,
        json={"method": "offline_transfer", "external_ref": "TX20260817", "note": "已转账"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"
    assert paid.json()["external_ref"] == "TX20260817"

    final = client.get("/api/v1/member/promotion", headers=mheaders).json()
    assert final["balance"] == "0.00"
    assert final["frozen_amount"] == "0.00"
    assert final["total_withdrawn"] == "80.00"

    history = client.get("/api/v1/member/promotion/withdrawals", headers=mheaders).json()
    assert history["total"] == 2
    assert {row["status"] for row in history["items"]} == {"paid", "rejected"}

    kinds = [
        row["kind"]
        for row in client.get("/api/v1/member/promotion/ledgers", headers=mheaders).json()["items"]
    ]
    assert kinds == [
        "withdraw_paid",
        "withdraw_freeze",
        "withdraw_revert",
        "withdraw_freeze",
        "adjust",
    ]


def test_withdraw_hold_days_blocks_recent_rebate(client: TestClient, admin_headers: dict):
    """返点冷却期内不可提现；冷却关闭后可按余额提现。"""
    gym_id = _gym_id(client, admin_headers)
    client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={
            "default_rebate_rate": "0.05",
            "default_downline_discount_rate": "0",
            "min_withdraw_amount": "1.00",
            "withdraw_hold_days": 7,
        },
    )
    upline = _member(client, admin_headers, gym_id, "13570004001", "冷却上级")
    code = _my_code(client, admin_headers, upline["id"])
    _member_headers(client, "13570004002", gym_id, code)
    downline = client.get("/api/v1/members?q=13570004002", headers=admin_headers).json()["items"][0]
    product = _membership_product(client, admin_headers, gym_id, "冷却月卡", "1000.00")
    _purchase_and_pay(client, admin_headers, gym_id, downline["id"], product["id"])

    mheaders = _member_headers(client, "13570004001", gym_id)
    mine = client.get("/api/v1/member/promotion", headers=mheaders).json()
    assert mine["held_amount"] == "50.00"
    assert mine["available_balance"] == "0.00"
    assert mine["withdraw_hold_days"] == 7

    blocked = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "50.00"}
    )
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "rebate_hold"

    client.put(
        "/api/v1/promotion-settings",
        headers=admin_headers,
        json={"withdraw_hold_days": 0},
    )
    opened = client.get("/api/v1/member/promotion", headers=mheaders).json()
    assert opened["available_balance"] == "50.00"
    ok = client.post(
        "/api/v1/member/promotion/withdrawals", headers=mheaders, json={"amount": "50.00"}
    )
    assert ok.status_code == 200, ok.text


def test_coach_personal_pt_rate_and_self_service_payout(
    client: TestClient, admin_headers: dict
):
    """教练个人私教佣金比例生效，教练本人可查看佣金并申请提现。"""
    gym_id = _gym_id(client, admin_headers)
    staff = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "pt_rate_coach",
            "password": "Coach@123456",
            "display_name": "分成教练",
            "merchant_id": gym_id,
            "role_codes": ["gym_coach"],
        },
    )
    assert staff.status_code == 200, staff.text
    coach = client.post(
        "/api/v1/coaches",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "staff_user_id": staff.json()["id"],
            "member_id": new_coach_member(client, admin_headers, gym_id)["id"],
            "display_name": "分成教练",
            "hourly_rate": "300.00",
            "pt_commission_rate": "0.4",
        },
    )
    assert coach.status_code == 200, coach.text
    assert coach.json()["pt_commission_rate"] == "0.4000"
    coach_id = coach.json()["id"]

    member = _member(client, admin_headers, gym_id, "13570003001", "私教会员")
    product = client.post(
        "/api/v1/pt-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "私教 2 节",
            "price": "2000.00",
            "session_count": 2,
            "valid_days": 90,
            "all_coaches": True,
        },
    ).json()
    order = client.post(
        "/api/v1/pt-packages/purchase",
        headers=admin_headers,
        json={"merchant_id": gym_id, "member_id": member["id"], "product_id": product["id"]},
    ).json()
    client.post(
        f"/api/v1/orders/{order['id']}/pay/offline",
        headers=admin_headers,
        json={"channel": "offline_cash"},
    )
    package_id = client.get(
        f"/api/v1/pt-packages?merchant_id={gym_id}&member_id={member['id']}",
        headers=admin_headers,
    ).json()["items"][0]["id"]

    starts = datetime.now(timezone.utc) + timedelta(days=1)
    appointment = client.post(
        "/api/v1/pt-appointments",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "coach_id": coach_id,
            "package_id": package_id,
            "starts_at": starts.isoformat(),
            "ends_at": (starts + timedelta(hours=1)).isoformat(),
        },
    ).json()
    done = client.post(
        f"/api/v1/pt-appointments/{appointment['id']}/complete", headers=admin_headers
    )
    assert done.status_code == 200, done.text

    records = client.get(
        f"/api/v1/commission-records?merchant_id={gym_id}&scope=pt_session",
        headers=admin_headers,
    ).json()["items"]
    assert len(records) == 1
    # 单节单价 1000（实付 2000 / 2 节）× 40%
    assert records[0]["base_amount"] == "1000.00"
    assert records[0]["amount"] == "400.00"
    assert records[0]["rate"] == "0.4000"
    record_id = records[0]["id"]

    coach_login = client.post(
        "/api/v1/auth/login", json={"username": "pt_rate_coach", "password": "Coach@123456"}
    )
    assert coach_login.status_code == 200, coach_login.text
    cheaders = {"Authorization": f"Bearer {coach_login.json()['access_token']}"}

    profile = client.get("/api/v1/my/coach-profile", headers=cheaders)
    assert profile.status_code == 200, profile.text
    assert profile.json()["pt_commission_rate"] == "0.4000"

    summary = client.get("/api/v1/my/commission-summary", headers=cheaders).json()
    assert summary["pending_amount"] == "400.00"
    assert summary["settleable_amount"] == "0.00"
    assert [row["scope"] for row in summary["by_scope"]] == ["pt_session"]

    blocked = client.post("/api/v1/my/payouts", headers=cheaders, json={})
    assert blocked.status_code == 400
    assert blocked.json()["code"] == "no_settleable_records"

    confirmed = client.post(
        f"/api/v1/commission-records/{record_id}/status",
        headers=admin_headers,
        json={"status": "confirmed"},
    )
    assert confirmed.status_code == 200, confirmed.text

    settleable = client.get("/api/v1/my/commission-summary", headers=cheaders).json()
    assert settleable["settleable_amount"] == "400.00"
    assert settleable["settleable_count"] == 1

    payout = client.post("/api/v1/my/payouts", headers=cheaders, json={"note": "本月结算"})
    assert payout.status_code == 200, payout.text
    assert payout.json()["amount"] == "400.00"
    assert payout.json()["status"] == "requested"
    assert payout.json()["item_count"] == 1
    payout_id = payout.json()["id"]

    # 已锁定的提成不能重复提现
    duplicate = client.post("/api/v1/my/payouts", headers=cheaders, json={})
    assert duplicate.status_code == 400

    locked = client.get("/api/v1/my/commission-summary", headers=cheaders).json()
    assert locked["settleable_amount"] == "0.00"
    assert locked["withdrawing_amount"] == "400.00"

    paid = client.post(
        f"/api/v1/payouts/{payout_id}/pay",
        headers=admin_headers,
        json={"method": "offline_cash", "external_ref": "CASH-0817"},
    )
    assert paid.status_code == 200, paid.text
    assert paid.json()["status"] == "paid"

    settled = client.get(
        "/api/v1/my/commission-records?status=paid", headers=cheaders
    ).json()["items"]
    assert [row["id"] for row in settled] == [record_id]
    assert settled[0]["settled_at"]

    mine = client.get("/api/v1/my/payouts", headers=cheaders).json()
    assert mine["total"] == 1
    assert mine["items"][0]["status"] == "paid"

    # 教练只能看自己的数据，无权进入管理端提现列表
    forbidden = client.get("/api/v1/payouts", headers=cheaders)
    assert forbidden.status_code == 403
