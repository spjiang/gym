"""商户角色包（A+B）复制幂等。"""


def test_create_merchant_copies_gym_role_pack(client, admin_headers):
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    gym_type = next(t for t in types if t["code"] == "gym")
    r = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": gym_type["id"],
            "name": "角色包测试健身房",
            "status": "active",
            "subsystem_codes": ["gym"],
        },
    )
    assert r.status_code == 200, r.text
    mid = r.json()["id"]

    roles = client.get("/api/v1/rbac/roles", headers=admin_headers).json()
    codes = {row["code"] for row in roles if row.get("merchant_id") == mid}
    assert {"gym_admin", "gym_ops", "gym_coach"} <= codes


def test_create_bar_merchant_copies_catering_pack(client, admin_headers):
    types = client.get("/api/v1/merchant-types", headers=admin_headers).json()
    bar_type = next(t for t in types if t["code"] == "bar")
    r = client.post(
        "/api/v1/merchants",
        headers=admin_headers,
        json={
            "merchant_type_id": bar_type["id"],
            "name": "角色包测试清吧",
            "status": "active",
            "subsystem_codes": ["catering"],
        },
    )
    assert r.status_code == 200, r.text
    mid = r.json()["id"]
    roles = client.get("/api/v1/rbac/roles", headers=admin_headers).json()
    codes = {row["code"] for row in roles if row.get("merchant_id") == mid}
    assert {"bar_admin", "bar_ops", "bar_cashier"} <= codes


def test_assignable_excludes_templates(client, admin_headers):
    rows = client.get("/api/v1/rbac/roles/assignable", headers=admin_headers).json()
    assert all(not r["code"].startswith("tpl_") for r in rows)
