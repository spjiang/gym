"""微信支付配置与会员预下单。"""

from fastapi.testclient import TestClient


def test_payment_settings_mask_and_persist(client: TestClient, admin_headers: dict):
    put = client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={
            "mode": "wechat",
            "dry_run": True,
            "mp_app_id": "wx_test_app",
            "mch_id": "1900000001",
            "api_v3_key": "super-secret-key-32bytes-xxxxxx",
            "notify_url": "https://example.com/api/v1/payments/wechat/notify",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["mode"] == "wechat"
    assert body["mp_app_id"] == "wx_test_app"
    assert body["api_v3_key"]["configured"] is True
    assert "super-secret" not in str(body)

    got = client.get("/api/v1/site/payment-settings", headers=admin_headers)
    assert got.status_code == 200
    assert got.json()["source"] == "db"
    assert "super-secret" not in str(got.json())


def test_payment_settings_clear_secret(client: TestClient, admin_headers: dict):
    put = client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={
            "mode": "wechat",
            "dry_run": True,
            "mp_app_secret": "mini-secret",
            "mch_private_key": "-----BEGIN PRIVATE KEY-----\nMIIB\n-----END PRIVATE KEY-----",
            "platform_public_key": "-----BEGIN PUBLIC KEY-----\nMFww\n-----END PUBLIC KEY-----",
        },
    )
    assert put.status_code == 200, put.text
    body = put.json()
    assert body["mp_app_secret"]["configured"] is True
    assert body["mch_private_key"]["configured"] is True
    assert body["platform_public_key"]["configured"] is True

    keep = client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={"mch_id": "1900000099"},
    )
    assert keep.status_code == 200, keep.text
    assert keep.json()["mp_app_secret"]["configured"] is True
    assert keep.json()["mch_private_key"]["configured"] is True
    assert keep.json()["platform_public_key"]["configured"] is True
    assert keep.json()["mch_id"] == "1900000099"

    cleared = client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={"mp_app_secret": "", "mch_private_key": "", "platform_public_key": ""},
    )
    assert cleared.status_code == 200, cleared.text
    assert cleared.json()["mp_app_secret"]["configured"] is False
    assert cleared.json()["mch_private_key"]["configured"] is False
    assert cleared.json()["platform_public_key"]["configured"] is False
    assert cleared.json()["mch_id"] == "1900000099"


def _member_token(client: TestClient, admin_headers: dict, *, phone: str, name: str) -> tuple[dict, int]:
    from app.core.config import get_settings

    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": phone, "name": name, "merchant_id": gym_id},
    )
    assert member.status_code == 200, member.text
    client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    return {"Authorization": f"Bearer {verify.json()['access_token']}"}, member.json()["id"]


def test_mini_bind_moves_openid_to_current_member(client: TestClient, admin_headers: dict):
    client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={"mode": "wechat", "dry_run": True, "mp_app_id": "wx_app", "mch_id": "mch1", "api_v3_key": "k" * 32},
    )
    headers_a, member_a = _member_token(client, admin_headers, phone="13980009911", name="绑定甲")
    headers_b, _member_b = _member_token(client, admin_headers, phone="13980009912", name="绑定乙")
    code = {"code": "samewxcode0001"}
    first = client.post("/api/v1/member/auth/wechat/mini/bind", headers=headers_a, json=code)
    assert first.status_code == 200, first.text
    again = client.post("/api/v1/member/auth/wechat/mini/bind", headers=headers_a, json=code)
    assert again.status_code == 200, again.text
    assert again.json()["mp_openid"] == first.json()["mp_openid"]

    moved = client.post("/api/v1/member/auth/wechat/mini/bind", headers=headers_b, json=code)
    assert moved.status_code == 200, moved.text
    assert moved.json()["mp_openid"] == first.json()["mp_openid"]

    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member_a,
            "order_type": "retail",
            "title": "原会员已无 openid",
            "amount": "1.00",
        },
    ).json()
    prepay = client.post(
        f"/api/v1/member/orders/{order['id']}/pay/online",
        headers=headers_a,
        json={"pay_scene": "miniprogram"},
    )
    assert prepay.status_code == 400, prepay.text
    assert prepay.json()["code"] == "openid_required"


def test_member_wechat_dry_run_pay_flow(client: TestClient, admin_headers: dict):
    client.put(
        "/api/v1/site/payment-settings",
        headers=admin_headers,
        json={"mode": "wechat", "dry_run": True, "mp_app_id": "wx_app", "mch_id": "mch1", "api_v3_key": "k" * 32},
    )
    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    member = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13980009901", "name": "支付会员", "merchant_id": gym_id},
    ).json()

    # 会员 OTP 登录
    from app.core.config import get_settings

    phone = "13980009901"
    client.post("/api/v1/member/auth/otp/send", json={"phone": phone})
    verify = client.post(
        "/api/v1/member/auth/otp/verify",
        json={"phone": phone, "code": get_settings().member_otp_mock_code},
    )
    assert verify.status_code == 200, verify.text
    mheaders = {"Authorization": f"Bearer {verify.json()['access_token']}"}

    bind = client.post("/api/v1/member/auth/wechat/mini/bind", headers=mheaders, json={"code": "testcode123"})
    assert bind.status_code == 200, bind.text
    assert bind.json()["mp_openid"].startswith("mock_mp_")

    order = client.post(
        "/api/v1/orders",
        headers=admin_headers,
        json={
            "merchant_id": gym_id,
            "member_id": member["id"],
            "order_type": "retail",
            "title": "微信支付测试",
            "amount": "1.00",
        },
    ).json()

    prepay = client.post(
        f"/api/v1/member/orders/{order['id']}/pay/online",
        headers=mheaders,
        json={"pay_scene": "miniprogram"},
    )
    assert prepay.status_code == 200, prepay.text
    data = prepay.json()
    assert data["status"] == "pending"
    assert data["dry_run"] is True
    assert data["jsapi_params"]
    assert data["out_trade_no"]

    confirm = client.post(
        f"/api/v1/member/orders/{order['id']}/pay/dry-run-confirm",
        headers=mheaders,
        json={"out_trade_no": data["out_trade_no"]},
    )
    assert confirm.status_code == 200, confirm.text
    assert confirm.json()["status"] == "paid"
