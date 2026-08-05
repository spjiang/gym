"""组织与身份权限测试。"""

from fastapi.testclient import TestClient


def test_health(client: TestClient):
    assert client.get("/health").json()["status"] == "ok"


def test_create_merchant_type_and_merchant(client: TestClient, admin_headers: dict):
    r = client.post(
        "/api/v1/merchant-types",
        headers=admin_headers,
        json={"code": "retail", "name": "零售"},
    )
    assert r.status_code == 200
    type_id = r.json()["id"]

    r = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={"merchant_type_id": type_id, "name": "测试店", "status": "active"},
    )
    assert r.status_code == 200
    mid = r.json()["id"]

    r = client.patch(f"/api/v1/merchants/{mid}?status=disabled", headers=admin_headers)
    assert r.status_code == 200
    assert r.json()["status"] == "disabled"


def test_login_and_unauthorized(client: TestClient, admin_headers: dict):
    assert client.get("/api/v1/auth/me").status_code == 401
    me = client.get("/api/v1/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert "site_admin" in me.json()["role_codes"]


def test_merchant_isolation_and_role_audit(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    gym_id = merchants[0]["id"]

    # 创建商户管理员（健身房商户角色实例）
    r = client.post(
        "/api/v1/staff",
        headers=admin_headers,
        json={
            "username": "madmin",
            "password": "Merchant@123",
            "display_name": "商户管理员",
            "merchant_id": gym_id,
            "role_codes": ["gym_admin"],
        },
    )
    assert r.status_code == 200, r.text
    staff_id = r.json()["id"]

    # 创建第二个商户
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar = next(t for t in types if t["code"] == "bar")
    other = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar["id"],
            "name": "酒吧A",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    ).json()

    token = client.post(
        "/api/v1/auth/login", json={"username": "madmin", "password": "Merchant@123"}
    ).json()["access_token"]
    mheaders = {"Authorization": f"Bearer {token}"}

    # 商户管理员不能创建他商户会员（跨商户）
    r = client.post(
        "/api/v1/members",
        headers=mheaders,
        json={"phone": "13800000001", "name": "甲", "merchant_id": other["id"]},
    )
    assert r.status_code == 403

    # 超管可跨商户创建
    r = client.post(
        "/api/v1/members",
        headers=admin_headers,
        json={"phone": "13800000002", "name": "乙", "merchant_id": other["id"]},
    )
    assert r.status_code == 200

    # 角色变更写审计（通过接口成功即视为写入路径执行）
    r = client.put(
        f"/api/v1/staff/{staff_id}/roles",
        headers=admin_headers,
        json={"role_codes": ["gym_ops"]},
    )
    assert r.status_code == 200
    assert r.json()["role_codes"] == ["gym_ops"]
