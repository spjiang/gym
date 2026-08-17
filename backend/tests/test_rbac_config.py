"""RBAC 配置与子系统导航测试。"""

from fastapi.testclient import TestClient

from app.systems.platform.models.rbac_catalog import MenuDef, PermissionDef, RoleMenu, RolePermission, Subsystem


def test_rbac_models_importable():
    assert Subsystem.__tablename__ == "subsystems"
    assert PermissionDef.__tablename__ == "permission_defs"
    assert MenuDef.__tablename__ == "menu_defs"
    assert RolePermission.__tablename__ == "role_permissions"
    assert RoleMenu.__tablename__ == "role_menus"


def test_sync_manifests_via_seed(client: TestClient, admin_headers: dict):
    r = client.get("/api/v1/rbac/subsystems", headers=admin_headers)
    assert r.status_code == 200, r.text
    codes = {x["code"] for x in r.json()}
    assert codes >= {"platform", "gym", "catering"}


def test_gym_navigation_splits_ops_and_config(client: TestClient, admin_headers: dict):
    nav = client.get("/api/v1/me/navigation", headers=admin_headers)
    assert nav.status_code == 200, nav.text
    gym_paths = {m["path"] for m in nav.json()["menus"] if m["subsystem_code"] == "gym"}
    assert {
        "/memberships",
        "/group-courses",
        "/group-bookings",
        "/pt-packages",
        "/coach-desk",
        "/retail",
        "/retail-categories",
        "/retail-products",
        "/products",
        "/pt-products",
        "/group-templates",
        "/coaches",
        "/equipment",
        "/equipment-repairs",
    } <= gym_paths
    # 办卡/续卡/收银不单独占菜单，走运营页内弹窗
    assert "/memberships/purchase" not in gym_paths
    assert "/memberships/renew" not in gym_paths
    assert "/retail/sell" not in gym_paths


def test_disable_gym_hides_from_navigation(client: TestClient, admin_headers: dict):
    patch = client.patch(
        "/api/v1/rbac/subsystems/gym",
        headers=admin_headers,
        json={"is_enabled": False},
    )
    assert patch.status_code == 200, patch.text
    nav = client.get("/api/v1/me/navigation", headers=admin_headers)
    assert nav.status_code == 200, nav.text
    assert all(m["subsystem_code"] != "gym" for m in nav.json()["menus"])
    # 恢复，避免影响其它用例顺序依赖
    client.patch("/api/v1/rbac/subsystems/gym", headers=admin_headers, json={"is_enabled": True})


def test_bar_role_cannot_grant_membership_perm(client: TestClient, admin_headers: dict):
    merchants = client.get("/api/v1/merchants", headers=admin_headers).json()
    bar = next(m for m in merchants if "catering" in (m.get("subsystem_codes") or []))
    created = client.post(
        "/api/v1/rbac/roles",
        headers=admin_headers,
        json={"code": "bar_custom", "name": "清吧自定义", "merchant_id": bar["id"]},
    )
    assert created.status_code == 200, created.text
    rid = created.json()["id"]
    bad = client.put(
        f"/api/v1/rbac/roles/{rid}/grants",
        headers=admin_headers,
        json={"permission_codes": ["membership:sell"], "menu_codes": []},
    )
    assert bad.status_code == 403, bad.text
    ok = client.put(
        f"/api/v1/rbac/roles/{rid}/grants",
        headers=admin_headers,
        json={"permission_codes": ["catering:order"], "menu_codes": ["catering.orders"]},
    )
    assert ok.status_code == 200, ok.text
