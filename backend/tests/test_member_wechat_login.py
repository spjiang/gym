"""会员 H5 微信快捷登录：未绑定先出票据，手机号验证后绑定，再登即进。"""

from fastapi.testclient import TestClient

from app.core.config import get_settings


def _enable_wechat(client: TestClient, admin_headers: dict) -> None:
    put = client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={
            "mode": "wechat",
            "dry_run": True,
            "oa_app_id": "wx_oa_test",
            "mp_app_id": "wx_mp_test",
            "mch_id": "1900000001",
            "api_v3_key": "k" * 32,
        },
    )
    assert put.status_code == 200, put.text


def test_wechat_oa_login_bind_then_signin(client: TestClient, admin_headers: dict):
    _enable_wechat(client, admin_headers)
    cfg = client.get("/api/v1/member/auth/wechat/oa/config")
    assert cfg.status_code == 200
    assert cfg.json()["oa_app_id"] == "wx_oa_test"
    assert cfg.json()["ready"] is True

    first = client.post("/api/v1/member/auth/wechat/oa", json={"code": "oa-login-code-001"})
    assert first.status_code == 200, first.text
    body = first.json()
    assert body["need_bind"] is True
    assert body["ticket"]
    assert body["access_token"] is None

    phone = "13980008801"
    assert client.post("/api/v1/member/auth/otp/send", json={"phone": phone}).status_code == 200
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={
            "phone": phone,
            "code": get_settings().member_otp_mock_code,
            "wechat_ticket": body["ticket"],
        },
    )
    assert verify.status_code == 200, verify.text
    assert verify.json()["access_token"]

    again = client.post("/api/v1/member/auth/wechat/oa", json={"code": "oa-login-code-001"})
    assert again.status_code == 200, again.text
    assert again.json()["need_bind"] is False
    assert again.json()["access_token"]


def test_wechat_oa_ticket_cannot_bind_second_member(client: TestClient, admin_headers: dict):
    _enable_wechat(client, admin_headers)
    first = client.post("/api/v1/member/auth/wechat/oa", json={"code": "oa-taken-code-002"}).json()
    phone_a = "13980008802"
    client.post("/api/v1/member/auth/otp/send", json={"phone": phone_a})
    assert (
        client.post(
            "/api/v1/member/auth/otp/verify",
            json={
                "phone": phone_a,
                "code": get_settings().member_otp_mock_code,
                "wechat_ticket": first["ticket"],
            },
        ).status_code
        == 200
    )

    pending = client.post("/api/v1/member/auth/wechat/oa", json={"code": "oa-taken-code-002"}).json()
    # 已绑定则直接登录，不再给别人绑定
    assert pending["access_token"]
    assert pending["need_bind"] is False
