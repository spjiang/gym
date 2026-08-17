"""商户角色包（A+B）复制幂等。"""

from sqlalchemy import select

from app.core import db as db_module
from app.core.manifest_sync import sync_manifests
from app.systems.platform.models.identity import Role
from app.systems.platform.models.rbac_catalog import RoleMenu


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


def test_existing_pack_gains_new_template_menus(client, admin_headers):
    db = db_module.SessionLocal()
    try:
        inst = db.scalar(select(Role).where(Role.code == "gym_admin", Role.merchant_id.is_not(None)))
        assert inst is not None
        row = db.scalar(
            select(RoleMenu).where(
                RoleMenu.role_id == inst.id, RoleMenu.menu_code == "gym.group_templates"
            )
        )
        if row is not None:
            db.delete(row)
            db.commit()
        sync_manifests(db)
        db.commit()
        restored = db.scalar(
            select(RoleMenu).where(
                RoleMenu.role_id == inst.id, RoleMenu.menu_code == "gym.group_templates"
            )
        )
        assert restored is not None
    finally:
        db.close()


def test_assignable_excludes_templates(client, admin_headers):
    rows = client.get("/api/v1/rbac/roles/assignable", headers=admin_headers).json()
    assert all(not r["code"].startswith("tpl_") for r in rows)


def test_gym_ops_gets_booking_desk_not_schedule(client, admin_headers):
    """前台看代约，不看排课；教练只看签到。"""
    db = db_module.SessionLocal()
    try:
        ops = db.scalar(select(Role).where(Role.code == "gym_ops", Role.merchant_id.is_not(None)))
        admin = db.scalar(select(Role).where(Role.code == "gym_admin", Role.merchant_id.is_not(None)))
        coach = db.scalar(select(Role).where(Role.code == "gym_coach", Role.merchant_id.is_not(None)))
        assert ops and admin and coach
        ops_menus = set(db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == ops.id)).all())
        admin_menus = set(db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == admin.id)).all())
        coach_menus = set(db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == coach.id)).all())
        assert "gym.group_bookings" in ops_menus
        assert "gym.group_courses" not in ops_menus
        assert "gym.coach_desk" in ops_menus
        assert {"gym.group_courses", "gym.group_bookings", "gym.coach_desk"} <= admin_menus
        assert "gym.coach_desk" in coach_menus
        assert "gym.group_bookings" not in coach_menus
        assert "gym.group_courses" not in coach_menus
    finally:
        db.close()


def test_stale_schedule_menu_revoked_without_manage(client, admin_headers):
    db = db_module.SessionLocal()
    try:
        ops = db.scalar(select(Role).where(Role.code == "gym_ops", Role.merchant_id.is_not(None)))
        assert ops is not None
        db.add(RoleMenu(role_id=ops.id, menu_code="gym.group_courses"))
        db.commit()
        sync_manifests(db)
        db.commit()
        leftover = db.scalar(
            select(RoleMenu).where(RoleMenu.role_id == ops.id, RoleMenu.menu_code == "gym.group_courses")
        )
        assert leftover is None
    finally:
        db.close()
