"""会员推广码公开解析：扫码落地累计访问。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _gym_id(client: TestClient, headers: dict) -> int:
    return client.get("/api/v1/merchants", headers=headers).json()[0]["id"]


def test_member_promotion_code_public_resolve(client: TestClient, admin_headers: dict):
    """会员码可被公开解析并累计访问；无效码返回 404。"""
    gym_id = _gym_id(client, admin_headers)
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13560000001", "name": "推广达人", "merchant_id": gym_id},
    ).json()
    promotion = client.get(f"/api/v1/members/{member['id']}/promotion", headers=admin_headers)
    assert promotion.status_code == 200, promotion.text
    code = promotion.json()["code"]
    assert code

    landing = client.get(f"/api/v1/promotions/{code.lower()}")
    assert landing.status_code == 200, landing.text
    assert landing.json()["code"] == code
    assert "推广达人" in landing.json()["name"]

    again = client.get(f"/api/v1/promotions/{code}")
    assert again.status_code == 200
    detail = client.get(f"/api/v1/members/{member['id']}/promotion", headers=admin_headers).json()
    assert detail["visit_count"] >= 2

    gone = client.get("/api/v1/promotions/NOTEXIST")
    assert gone.status_code == 404

    # 管理端人工推广位已下线
    created = client.post(
        "/api/v1/promoters",
        headers=admin_headers,
        json={"name": "渠道物料", "subject_type": "channel", "channel": "poster"},
    )
    assert created.status_code == 404
    nav = client.get("/api/v1/me/navigation", headers=admin_headers)
    assert nav.status_code == 200, nav.text
    paths = {m["path"] for m in nav.json()["menus"]}
    assert "/promoters" not in paths
    assert "/platform/promotion-settings" in paths
    assert "/platform/promotion-config" in paths


def test_member_otp_bind_via_promotion_code(client: TestClient, admin_headers: dict):
    """扫码注册仍绑定会员推荐人。"""
    gym_id = _gym_id(client, admin_headers)
    upline = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13560000011", "name": "码主", "merchant_id": gym_id},
    ).json()
    code = client.get(f"/api/v1/members/{upline['id']}/promotion", headers=admin_headers).json()["code"]
    payload = {"phone": "13560000012", "merchant_id": gym_id}
    assert client.post("/api/v1/member/auth/otp/send", json=payload).status_code == 200
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={**payload, "code": get_settings().member_otp_mock_code, "referral_code": code},
    )
    assert verify.status_code == 200, verify.text
    downline = client.get("/api/v1/members?q=13560000012", headers=admin_headers).json()["items"][0]
    assert downline["referrer_member_id"] == upline["id"]
