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
    assert saved.json()["api_key"] == "ak-test"
    assert saved.json()["api_secret"] == "sk-test"
    assert saved.json()["sign_name"] == "观野SPACE"
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


def test_aliyun_otp_uses_scene_template(client: TestClient, admin_headers: dict, monkeypatch):
    sent: dict = {}

    def fake_send(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("app.systems.platform.services.otp.send_aliyun_sms", fake_send)
    client.put(
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
    client.post(
        "/api/v1/site/sms/templates",
        headers=admin_headers,
        json={
            "code": "SMS_LOGIN",
            "name": "登录验证码",
            "content": "您正在登录，验证码${code}",
            "scene": "login",
            "is_enabled": True,
        },
    )
    client.post(
        "/api/v1/site/sms/templates",
        headers=admin_headers,
        json={
            "code": "SMS_REGISTER",
            "name": "注册验证码",
            "content": "您正在注册账号，验证码${code}",
            "scene": "register",
            "is_enabled": True,
        },
    )
    send = client.post("/api/v1/member/auth/otp/send", json={"phone": "13881116602", "scene": "register"})
    assert send.status_code == 200, send.text
    assert sent["template_code"] == "SMS_REGISTER"


def test_sms_template_test_send(client: TestClient, admin_headers: dict, monkeypatch):
    sent: dict = {}

    def fake_send(**kwargs):
        sent.update(kwargs)

    monkeypatch.setattr("app.systems.platform.api.sms.send_aliyun_sms", fake_send)
    client.put(
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
    created = client.post(
        "/api/v1/site/sms/templates",
        headers=admin_headers,
        json={
            "code": "SMS_TEST_SEND",
            "name": "登录测试",
            "scene": "login",
            "is_enabled": True,
        },
    )
    assert created.status_code == 200, created.text
    template_id = created.json()["id"]
    tested = client.post(
        f"/api/v1/site/sms/templates/{template_id}/test",
        headers=admin_headers,
        json={"phone": "13800138000"},
    )
    assert tested.status_code == 200, tested.text
    assert sent["template_code"] == "SMS_TEST_SEND"
    assert sent["phone"] == "13800138000"
    assert sent["template_param"]["code"] == tested.json()["code"]
    bad = client.post(
        f"/api/v1/site/sms/templates/{template_id}/test",
        headers=admin_headers,
        json={"phone": "123"},
    )
    assert bad.status_code == 400
