"""会员自助领券与体验卡种。"""

from datetime import datetime, timedelta, timezone

from fastapi.testclient import TestClient

from app.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def _member_headers(client: TestClient, phone: str) -> dict:
    assert client.post("/api/v1/member/auth/otp/send", json={"phone": phone}).status_code == 200
    code = get_settings().member_otp_mock_code
    verify = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_member_claim_coupon_and_limit(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    now = datetime.now(timezone.utc)
    starts = (now - timedelta(hours=1)).isoformat()
    ends = (now + timedelta(days=7)).isoformat()

    tpl = client.post(
        "/api/v1/coupons/templates",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "新人满减",
            "discount_type": "fixed",
            "threshold_amount": "0",
            "fixed_amount": "10.00",
            "applicable_to": "both",
            "starts_at": starts,
            "ends_at": ends,
            "total_limit": 5,
            "claimable": True,
            "per_member_limit": 1,
        },
    )
    assert tpl.status_code == 200, tpl.text
    template_id = tpl.json()["id"]
    assert tpl.json()["claimable"] is True

    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13640000001", "name": "领券客", "merchant_id": gym_id},
    ).json()
    mheaders = _member_headers(client, member["phone"])

    claimable = client.get(
        f"/api/v1/member/coupons/claimable?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert claimable.status_code == 200
    assert any(c["id"] == template_id for c in claimable.json())

    claimed = client.post(
        "/api/v1/member/coupons/claim",
        headers=mheaders,
        json={"merchant_id": gym_id, "template_id": template_id},
    )
    assert claimed.status_code == 200, claimed.text
    assert claimed.json()["status"] == "unused"

    again = client.post(
        "/api/v1/member/coupons/claim",
        headers=mheaders,
        json={"merchant_id": gym_id, "template_id": template_id},
    )
    assert again.status_code == 400
    assert again.json()["code"] == "coupon_member_limit"

    mine = client.get(f"/api/v1/member/coupons?merchant_id={gym_id}", headers=mheaders).json()
    assert len(mine) == 1


def test_trial_membership_product_catalog(client: TestClient, admin_headers: dict):
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13640000002", "name": "体验客", "merchant_id": gym_id},
    ).json()
    point = client.post(
        "/api/v1/access-points",
        headers=admin_headers,
        json={"name": "体验门", "merchant_id": gym_id},
    ).json()
    product = client.post(
        "/api/v1/membership-products",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "name": "三日体验",
            "product_type": "term",
            "price": "19.00",
            "duration_days": 3,
            "access_point_ids": [point["id"]],
            "is_active": True,
            "is_trial": True,
        },
    )
    assert product.status_code == 200, product.text
    assert product.json()["is_trial"] is True

    mheaders = _member_headers(client, member["phone"])
    catalog = client.get(
        f"/api/v1/member/catalog/membership-products?merchant_id={gym_id}",
        headers=mheaders,
    )
    assert catalog.status_code == 200
    row = next(p for p in catalog.json() if p["id"] == product.json()["id"])
    assert row["is_trial"] is True
