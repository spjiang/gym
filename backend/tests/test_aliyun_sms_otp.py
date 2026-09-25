"""阿里云短信验证码：启用后不再走 mock 码。"""

from fastapi.testclient import TestClient


def test_aliyun_otp_sends_template_code(client: TestClient, admin_headers: dict, monkeypatch):
    sent: dict = {}

    def fake_send(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("app.systems.platform.services.otp.send_aliyun_sms", fake_send)
    saved = client.put(
        "/api/v1/site/sms/settings",
        headers=admin_headers,
        json={
            "provider": "aliyun",
            "enabled": True,
            "sign_name": "观野SPACE",
            "api_key": "ak-test",
            "api_secret": "sk-test",
        },
    )
    assert saved.status_code == 200, saved.text
    created = client.post(
        "/api/v1/site/sms/templates",
        headers=admin_headers,
        json={
            "code": "SMS_TEST_OTP",
            "name": "登录验证码",
            "content": "您的验证码为${code}",
            "scene": "otp",
            "is_enabled": True,
        },
    )
    assert created.status_code == 200, created.text

    phone = "13881116601"
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    assert send.status_code == 200, send.text
    assert sent["phone"] == phone
    assert sent["sign_name"] == "观野SPACE"
    assert sent["template_code"] == "SMS_TEST_OTP"
    code = sent["template_param"]["code"]
    assert code != "123456"
    verified = client.post("/api/v1/member/auth/otp/verify", json={"phone": phone, "code": code})
    assert verified.status_code == 200, verified.text
