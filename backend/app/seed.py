"""种子数据：场地、商户类型、示例商户、角色、超管；可选目录级 Demo。"""

import app.models  # noqa: F401 — 注册全部表元数据，避免跨模块 FK 在 flush 时找不到 orders 等表

from datetime import date

from sqlalchemy import select

from app.core import db as db_module
from app.core.config import get_settings
from app.core.domain.subsystems import replace_merchant_subsystems
from app.core.manifest_sync import sync_manifests, sync_role_permissions_from_json
from app.core.security import hash_password
from app.seed_demo import seed_demo_catalog
from app.seed_demo_ops import seed_demo_operations
from app.seed_reset import reset_all_data
from app.systems.platform.models.access import AccessPoint
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.models.org import Merchant, MerchantContact, MerchantStatus, MerchantType, Site
from app.systems.platform.services.role_packs import ensure_merchant_role_packs


def _ensure_merchant_profile(
    db,
    merchant: Merchant,
    *,
    legal_name: str,
    credit_code: str,
    license_no: str,
    legal_person: str,
    registered_address: str,
    business_address: str,
    contact_phone: str,
    business_hours: str,
    description: str,
    contacts: list[tuple[str, str, str, str]],
    lease_starts_on: date | None = None,
    lease_ends_on: date | None = None,
    tagline: str | None = None,
) -> None:
    """补齐演示商户证照、租期与联系人；已有档案则只补空字段。"""
    if not merchant.legal_name:
        merchant.legal_name = legal_name
    if not merchant.credit_code:
        merchant.credit_code = credit_code
    if not merchant.license_no:
        merchant.license_no = license_no
    if not merchant.legal_person:
        merchant.legal_person = legal_person
    if not merchant.registered_address:
        merchant.registered_address = registered_address
    if not merchant.business_address:
        merchant.business_address = business_address
    if not merchant.contact_phone:
        merchant.contact_phone = contact_phone
    if not merchant.business_hours:
        merchant.business_hours = business_hours
    if not merchant.description:
        merchant.description = description
    elif merchant.description in {"观野FIT 健身空间", "观野BAR 酒吧"} and description:
        merchant.description = description
    if tagline and not merchant.tagline:
        merchant.tagline = tagline
    if merchant.lease_starts_on is None and lease_starts_on is not None:
        merchant.lease_starts_on = lease_starts_on
    if merchant.lease_ends_on is None and lease_ends_on is not None:
        merchant.lease_ends_on = lease_ends_on
    existing = db.scalar(select(MerchantContact.id).where(MerchantContact.merchant_id == merchant.id))
    if existing is None:
        for index, (name, phone, title, kind) in enumerate(contacts):
            db.add(
                MerchantContact(
                    merchant_id=merchant.id,
                    name=name,
                    phone=phone,
                    title=title,
                    kind=kind,
                    sort_order=index,
                )
            )

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
            "promoter:read",
            "promoter:manage",
            "payout:read",
            "payout:manage",
            "audit:read",
            "ai:read",
            "ai:manage",
        ],
    },
    {
        "code": "site_finance",
        "name": "场地财务人员",
        "is_site_scope": True,
        "permissions": [
            "system:platform",
            "system:gym",
            "system:catering",
            "org:read",
            "member:read",
            "order:read",
            "report:read",
            "payment:reconcile",
            "payout:read",
            "payout:manage",
            "promoter:read",
            "commission:read",
            "audit:read",
            "ai:read",
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
            "pt:book",
            "activity:manage",
            "activity:register",
            "commission:read",
            "commission:manage",
            "sales:manage",
            "promoter:read",
            "promoter:manage",
            "payout:read",
            "payout:manage",
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
            "audit:read",
            "ai:read",
        ],
    },
    {
        "code": "tpl_gym_front",
        "name": "健身房前台",
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
            "pt:book",
            "activity:register",
            "promoter:read",
            "retail:sell",
            "retail:read",
            "coupon:redeem",
            "coupon:read",
            "equipment:repair",
            "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_ops",
        "name": "健身房运营",
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
            "pt:book",
            "activity:register",
            "commission:read",
            "promoter:read",
            "payout:read",
            "retail:sell",
            "retail:read",
            "coupon:redeem",
            "coupon:read",
            "equipment:repair",
            "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_sales",
        "name": "健身房销售",
        "is_site_scope": False,
        "permissions": [
            "system:platform",
            "system:gym",
            "member:read",
            "member:write",
            "order:read",
            "order:write",
            "membership:sell",
            "pt:sell",
            "activity:register",
            "commission:self",
            "promoter:read",
            "retail:sell",
            "retail:read",
            "coupon:redeem",
            "coupon:read",
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
            "pt:book",
            "commission:self",
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
        if settings.seed_reset_data:
            reset_all_data(db)
            db.commit()
            print("[seed] 已清空全部业务数据（SEED_RESET_DATA=true）")

        site = db.scalar(select(Site).order_by(Site.id))
        if site is None:
            site = Site(
                name="观野SPACE",
                address="北京市昌平区回龙观公园",
                tagline="运动 · 夜生活 · 社区",
                description=(
                    "观野SPACE 位于回龙观公园，汇聚观野FIT 与观野BAR。"
                    "白天训练恢复，夜晚社交相聚，一站式综合经营场地。"
                ),
                service_phone="010-88881001",
                business_hours="06:00–24:00",
            )
            db.add(site)
            db.flush()
        else:
            site.name = "观野SPACE"
        if not site.address:
            site.address = "北京市昌平区回龙观公园"
        if not site.tagline:
            site.tagline = "运动 · 夜生活 · 社区"
        if not site.description:
            site.description = (
                "观野SPACE 位于回龙观公园，汇聚观野FIT 与观野BAR。"
                "白天训练恢复，夜晚社交相聚，一站式综合经营场地。"
            )
        if not site.service_phone:
            site.service_phone = "010-88881001"
        if not site.business_hours:
            site.business_hours = "06:00–24:00"

        for code, name in (("gym", "观野FIT"), ("bar", "观野BAR")):
            mt = db.scalar(select(MerchantType).where(MerchantType.code == code))
            if mt is None:
                db.add(MerchantType(code=code, name=name))
                db.flush()
            else:
                mt.name = name

        gym_type = db.scalar(select(MerchantType).where(MerchantType.code == "gym"))
        bar_type = db.scalar(select(MerchantType).where(MerchantType.code == "bar"))
        gym = None
        if gym_type is not None:
            gym = db.scalar(
                select(Merchant).where(Merchant.merchant_type_id == gym_type.id).order_by(Merchant.id)
            )
            if gym is None:
                gym = Merchant(
                    site_id=site.id,
                    merchant_type_id=gym_type.id,
                    name="观野FIT",
                    status=MerchantStatus.ACTIVE.value,
                )
                db.add(gym)
                db.flush()
            else:
                gym.name = "观野FIT"
        bar = None
        if bar_type is not None:
            bar = db.scalar(
                select(Merchant).where(Merchant.merchant_type_id == bar_type.id).order_by(Merchant.id)
            )
            if bar is None:
                bar = Merchant(
                    site_id=site.id,
                    merchant_type_id=bar_type.id,
                    name="观野BAR",
                    status=MerchantStatus.ACTIVE.value,
                )
                db.add(bar)
                db.flush()
            else:
                bar.name = "观野BAR"

        if gym is not None:
            replace_merchant_subsystems(db, gym.id, ["gym"])
            _ensure_merchant_profile(
                db,
                gym,
                legal_name="北京观野健身服务有限公司",
                credit_code="91110108MA01FIT01X",
                license_no="91110108MA01FIT01X",
                legal_person="林观野",
                registered_address="北京市昌平区回龙观东大街综合场地",
                business_address="回龙观综合场地 · 观野FIT",
                contact_phone="010-88881001",
                business_hours="06:00-22:00",
                tagline="训练即生活",
                description="力量区、操房与私教工作室一体。从燃脂团课到一对一私教，把训练变成日常。",
                lease_starts_on=date(2025, 3, 1),
                lease_ends_on=date(2028, 2, 28),
                contacts=[
                    ("陈店长", "13800101001", "店长", "primary"),
                    ("值班经理", "13800101002", "值班经理", "emergency"),
                    ("物业对接", "13800101003", "物业", "emergency"),
                ],
            )
        if bar is not None:
            replace_merchant_subsystems(db, bar.id, ["catering"])
            _ensure_merchant_profile(
                db,
                bar,
                legal_name="北京观野餐饮管理有限公司",
                credit_code="91110108MA01BAR01X",
                license_no="91110108MA01BAR01X",
                legal_person="林观野",
                registered_address="北京市昌平区回龙观东大街综合场地",
                business_address="回龙观综合场地 · 观野BAR",
                contact_phone="010-88881002",
                business_hours="17:00-02:00",
                tagline="夜色刚刚开始",
                description="观野BAR 酒吧",
                lease_starts_on=date(2025, 9, 1),
                lease_ends_on=date(2026, 9, 5),
                contacts=[
                    ("赵店长", "13800102001", "店长", "primary"),
                    ("安保负责", "13800102002", "安保", "emergency"),
                ],
            )

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
                sync_role_permissions_from_json(db, role)
            else:
                if settings.seed_reset_roles or settings.seed_reset_data:
                    role.permissions = list(defn["permissions"])
                    role.name = defn["name"]
                    role.is_site_scope = defn["is_site_scope"]
                    if defn["code"] == "site_admin":
                        role.is_system = True
                    sync_role_permissions_from_json(db, role)
            role_map[defn["code"]] = role

        db.flush()
        sync_manifests(db, ensure_role_menus=True)

        from app.systems.platform.services.role_packs import sync_existing_role_packs

        sync_existing_role_packs(db)

        from app.systems.platform.services.ai_prompt_seed import seed_ai_prompt_templates

        seed_ai_prompt_templates(db, site.id)

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
            seed_demo_catalog(db, site=site, gym=gym, bar=bar, role_map=role_map)
            seed_demo_operations(db, site=site, gym=gym, bar=bar)
            print("[seed] Demo 目录与运营样本已就绪（SEED_DEMO=true）")
            print("[seed] 账号说明见 docs/Demo账号说明.md")
        else:
            print("[seed] 跳过 Demo 目录数据（SEED_DEMO=false）")

        db.commit()
        print("[seed] 完成：场地/类型/商户/角色包/超管已就绪")
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
