"""会员扫码获客：注册、挂靠、来源字段。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _otp_login(client: TestClient, phone: str, merchant_id: int | None = None) -> dict:
    payload: dict = {"phone": phone}
    if merchant_id is not None:
        payload["merchant_id"] = merchant_id
    send = client.post("/api/v1/member/auth/otp/send", json=payload)
    assert send.status_code == 200, send.text
    code = get_settings().member_otp_mock_code
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={**payload, "code": code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}


def test_qr_register_link_and_platform(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]
    # 确保有第二家店
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar_type = next(t for t in types if t["code"] == "bar")
    bar = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar_type["id"],
            "name": "获客测试清吧",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()
    bar_id = bar["id"]

    phone = "13880007701"
    h = _otp_login(client, phone, merchant_id=gym_id)
    me = client.get("/api/v1/member/me", headers=h).json()
    assert me["acquisition_source"] == "merchant"
    assert me["first_merchant_id"] == gym_id
    assert gym_id in me["merchant_ids"]
    assert me["first_merchant_name"]

    # 同号挂第二店，首次来源不变
    h2 = _otp_login(client, phone, merchant_id=bar_id)
    me2 = client.get("/api/v1/member/me", headers=h2).json()
    assert me2["id"] == me["id"]
    assert me2["first_merchant_id"] == gym_id
    assert set(me2["merchant_ids"]) >= {gym_id, bar_id}

    # 无商户参 → 平台来源
    phone2 = "13880007702"
    hp = _otp_login(client, phone2)
    mep = client.get("/api/v1/member/me", headers=hp).json()
    assert mep["acquisition_source"] == "platform"
    assert mep["first_merchant_id"] is None
    assert mep["merchant_ids"] == []


def test_acquisition_link(client: TestClient, admin_headers: dict):
    mid = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    resp = client.get(f"/api/v1/merchants/{mid}/acquisition-link", headers=admin_headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["merchant_id"] == mid
    assert f"merchant_id={mid}" in body["url"]
    assert body["url"].startswith("http")
