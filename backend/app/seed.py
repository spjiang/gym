"""种子数据：场地、商户类型、示例商户、角色、超管；可选目录级 Demo。"""

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import get_settings
from app.core.domain.subsystems import replace_merchant_subsystems
from app.core.manifest_sync import sync_manifests, sync_role_permissions_from_json
from app.core.security import hash_password
from app.seed_demo import seed_demo_catalog
from app.systems.platform.models.access import AccessPoint
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.models.org import Merchant, MerchantStatus, MerchantType, Site
from app.systems.platform.services.role_packs import ensure_merchant_role_packs

ROLE_DEFS = [
    {
        "code": "site_admin",
        "name": "场地管理员",
        "is_site_scope": True,
        "permissions": ["*"],
    },
    {
        "code": "site_ops",
        "name": "场地运营人员",
        "is_site_scope": True,
        "permissions": [
            "system:platform",
            "org:read",
            "member:read",
            "member:write",
            "access:read",
            "access:manage",
            "order:read",
            "order:write",
            "report:read",
        ],
    },
    {
        "code": "tpl_gym_admin",
        "name": "健身房管理员",
        "is_site_scope": False,
        "permissions": [
            "system:platform",
            "system:gym",
            "org:read",
            "staff:manage",
            "rbac:manage",
            "member:read",
            "member:write",
            "access:read",
            "access:manage",
            "order:read",
            "order:write",
            "membership:manage",
            "membership:sell",
            "coach:manage",
            "course:manage",
            "course:book",
            "course:checkin",
            "pt:sell",
            "retail:manage",
            "retail:sell",
            "retail:read",
            "coupon:manage",
            "coupon:redeem",
            "coupon:read",
            "report:read",
            "equipment:manage",
            "equipment:repair",
            "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_ops",
        "name": "健身房运营人员",
        "is_site_scope": False,
        "permissions": [
            "system:platform",
            "system:gym",
            "member:read",
            "member:write",
            "access:read",
            "access:manage",
            "order:read",
            "order:write",
            "membership:sell",
            "course:book",
            "course:checkin",
            "pt:sell",
            "retail:sell",
            "retail:read",
            "coupon:redeem",
            "coupon:read",
            "equipment:repair",
            "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_coach",
        "name": "健身房教练",
        "is_site_scope": False,
        "permissions": [
            "system:gym",
            "member:read",
            "course:checkin",
            "equipment:read",
            "equipment:repair",
        ],
    },
    {
        "code": "tpl_bar_admin",
        "name": "清吧管理人员",
        "is_site_scope": False,
        "permissions": [
            "system:platform",
            "system:catering",
            "org:read",
            "staff:manage",
            "rbac:manage",
            "member:read",
            "member:write",
            "access:read",
            "access:manage",
            "order:read",
            "order:write",
            "report:read",
            "catering:menu",
            "catering:order",
        ],
    },
    {
        "code": "tpl_bar_ops",
        "name": "清吧运营人员",
        "is_site_scope": False,
        "permissions": [
            "system:catering",
            "member:read",
            "order:read",
            "order:write",
            "catering:menu",
            "catering:order",
        ],
    },
    {
        "code": "tpl_bar_cashier",
        "name": "清吧收银人员",
        "is_site_scope": False,
        "permissions": [
            "system:catering",
            "member:read",
            "order:read",
            "order:write",
            "catering:order",
        ],
    },
]


def run_seed() -> None:
    settings = get_settings()
    db = db_module.SessionLocal()
    try:
        site = db.scalar(select(Site).order_by(Site.id))
        if site is None:
            site = Site(name="回龙观公园综合场地", address="北京市昌平区回龙观公园")
            db.add(site)
            db.flush()

        for code, name in (("gym", "健身房"), ("bar", "酒吧")):
            mt = db.scalar(select(MerchantType).where(MerchantType.code == code))
            if mt is None:
                db.add(MerchantType(code=code, name=name))
                db.flush()

        gym_type = db.scalar(select(MerchantType).where(MerchantType.code == "gym"))
        bar_type = db.scalar(select(MerchantType).where(MerchantType.code == "bar"))
        gym = db.scalar(select(Merchant).where(Merchant.name == "回龙观自营健身房"))
        if gym is None and gym_type is not None:
            gym = Merchant(
                site_id=site.id,
                merchant_type_id=gym_type.id,
                name="回龙观自营健身房",
                status=MerchantStatus.ACTIVE.value,
            )
            db.add(gym)
            db.flush()
        bar = db.scalar(select(Merchant).where(Merchant.name == "回龙观清吧"))
        if bar is None and bar_type is not None:
            bar = Merchant(
                site_id=site.id,
                merchant_type_id=bar_type.id,
                name="回龙观清吧",
                status=MerchantStatus.ACTIVE.value,
            )
            db.add(bar)
            db.flush()

        if gym is not None:
            replace_merchant_subsystems(db, gym.id, ["gym"])
        if bar is not None:
            replace_merchant_subsystems(db, bar.id, ["catering"])

        if gym is not None:
            existing_point = db.scalar(
                select(AccessPoint).where(
                    AccessPoint.site_id == site.id,
                    AccessPoint.merchant_id == gym.id,
                    AccessPoint.name == "健身房正门",
                )
            )
            if existing_point is None:
                db.add(
                    AccessPoint(
                        site_id=site.id,
                        merchant_id=gym.id,
                        name="健身房正门",
                        is_public_area=False,
                    )
                )
                db.flush()

        role_map: dict[str, Role] = {}
        for defn in ROLE_DEFS:
            role = db.scalar(
                select(Role).where(Role.code == defn["code"], Role.merchant_id.is_(None))
            )
            if role is None:
                role = Role(
                    code=defn["code"],
                    name=defn["name"],
                    permissions=defn["permissions"],
                    is_site_scope=defn["is_site_scope"],
                    merchant_id=None,
                    is_system=defn["code"] == "site_admin",
                )
                db.add(role)
                db.flush()
            else:
                role.permissions = list(defn["permissions"])
                role.name = defn["name"]
                role.is_site_scope = defn["is_site_scope"]
                if defn["code"] == "site_admin":
                    role.is_system = True
            sync_role_permissions_from_json(db, role)
            role_map[defn["code"]] = role

        db.flush()
        sync_manifests(db, ensure_role_menus=True)

        # 模板菜单就绪后再复制商户实例
        if gym is not None:
            ensure_merchant_role_packs(db, gym.id)
        if bar is not None:
            ensure_merchant_role_packs(db, bar.id)

        admin = db.scalar(select(StaffUser).where(StaffUser.username == settings.seed_admin_username))
        if admin is None:
            admin = StaffUser(
                site_id=site.id,
                merchant_id=None,
                username=settings.seed_admin_username,
                password_hash=hash_password(settings.seed_admin_password),
                display_name=settings.seed_admin_display_name,
                is_active=True,
            )
            db.add(admin)
            db.flush()
            db.add(StaffRole(staff_id=admin.id, role_id=role_map["site_admin"].id))

        if settings.seed_demo and gym is not None:
            seed_demo_catalog(db, site=site, gym=gym, role_map=role_map)
            print("[seed] Demo 目录数据已就绪（SEED_DEMO=true）")
        else:
            print("[seed] 跳过 Demo 目录数据（SEED_DEMO=false）")

        db.commit()
        print("[seed] 完成：场地/类型/商户/角色包/超管已就绪")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
