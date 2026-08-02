"""种子数据：场地、商户类型、示例商户、角色、超管。"""

from sqlalchemy import select

from app import db as db_module
from app.config import get_settings
from app.models.access import AccessPoint
from app.models.identity import Role, StaffRole, StaffUser
from app.models.org import Merchant, MerchantStatus, MerchantType, Site
from app.security import hash_password

ROLE_DEFS = [
    {
        "code": "site_admin",
        "name": "场地超管",
        "is_site_scope": True,
        "permissions": ["*"],
    },
    {
        "code": "merchant_admin",
        "name": "商户管理员",
        "is_site_scope": False,
        "permissions": [
            "org:read",
            "staff:manage",
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
        "code": "front_desk",
        "name": "前台",
        "is_site_scope": False,
        "permissions": [
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
            "retail:manage",
            "retail:sell",
            "retail:read",
            "coupon:manage",
            "coupon:redeem",
            "coupon:read",
            "equipment:repair",
            "equipment:read",
        ],
    },
    {
        "code": "coach",
        "name": "教练",
        "is_site_scope": False,
        "permissions": [
            "member:read",
            "access:read",
            "order:read",
            "course:checkin",
            "equipment:repair",
            "equipment:read",
        ],
    },
]


def run_seed() -> None:
    settings = get_settings()
    # 动态取 SessionLocal，便于测试替换引擎
    db = db_module.SessionLocal()
    try:
        site = db.scalar(select(Site).order_by(Site.id))
        if site is None:
            site = Site(name="回龙观公园综合场地", address="北京市昌平区回龙观公园")
            db.add(site)
            db.flush()

        for code, name in (("gym", "健身房"), ("bar", "酒吧")):
            if db.scalar(select(MerchantType).where(MerchantType.code == code)) is None:
                db.add(MerchantType(code=code, name=name, description=f"{name}业态"))

        db.flush()
        gym_type = db.scalar(select(MerchantType).where(MerchantType.code == "gym"))
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

        # 示例门禁点：会籍卡种启用售卖时必须绑定
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
            role = db.scalar(select(Role).where(Role.code == defn["code"]))
            if role is None:
                role = Role(
                    code=defn["code"],
                    name=defn["name"],
                    permissions=defn["permissions"],
                    is_site_scope=defn["is_site_scope"],
                )
                db.add(role)
                db.flush()
            else:
                # 合并权限点，支持后续切片增量
                merged = list(dict.fromkeys([*(role.permissions or []), *defn["permissions"]]))
                role.permissions = merged
                role.name = defn["name"]
                role.is_site_scope = defn["is_site_scope"]
            role_map[defn["code"]] = role

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

        db.commit()
        print("[seed] 完成：场地/类型/商户/角色/超管已就绪")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
