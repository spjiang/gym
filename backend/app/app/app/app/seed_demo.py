"""交付级 Demo 数据：覆盖各业务列表页，便于本地体验与演示交付。

幂等策略：按唯一业务键（用户名/手机号/名称/设备码等）存在则跳过。
不预置已支付订单或已履约会籍，避免污染正式流水语义。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401 — 注册 Order 等表，满足 StockMovement.order_id 外键解析
from app.systems.platform.models.access import AccessDevice, AccessPoint
from app.systems.gym.models.coupon import ApplicableTo, CouponTemplate, DiscountType, MemberCoupon, MemberCouponStatus
from app.systems.gym.models.activity import Activity, ActivityStatus
from app.systems.gym.models.course import Coach, GroupCourse, GroupSession, GroupSessionStatus, PtPackageProduct
from app.systems.gym.models.commission import (
    CommissionBasis,
    CommissionBeneficiary,
    CommissionRule,
    CommissionScope,
)
from app.systems.gym.models.sales import SalesRep
from app.systems.gym.models.equipment import EquipmentAsset, EquipmentStatus
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.services.promotion import ensure_member_promoter_code
from app.systems.gym.models.membership import MembershipProduct, MembershipProductAccessPoint, ProductType
from app.systems.platform.models.notification import Notification
from app.systems.platform.models.agreement import LegalAgreement
from app.systems.platform.models.org import Merchant, MerchantStatus, MerchantType, Site
from app.systems.gym.models.retail import ProductCategory, RetailSku, StockMovement, StockMovementType
from app.systems.catering.models.catering import CateringMenuCategory, CateringMenuItem, CateringTable
from app.systems.catering.services.tables import generate_table_code
from app.core.security import hash_device_api_key, hash_password
from app.systems.gym.services.sales_member import link_sales_member

UTC = timezone.utc
DEMO_PASSWORD = "Demo@123456"


def _now() -> datetime:
    return datetime.now(UTC)


def _get_or_create_staff(
    db: Session,
    *,
    site_id: int,
    merchant_id: int | None,
    username: str,
    password: str,
    display_name: str,
    role: Role,
) -> StaffUser:
    staff = db.scalar(select(StaffUser).where(StaffUser.username == username))
    if staff is None:
        staff = StaffUser(
            site_id=site_id,
            merchant_id=merchant_id,
            username=username,
            password_hash=hash_password(password),
            display_name=display_name,
            is_active=True,
        )
        db.add(staff)
        db.flush()
        db.add(StaffRole(staff_id=staff.id, role_id=role.id))
    return staff


def _ensure_staff_role(db: Session, staff: StaffUser, role: Role) -> None:
    """确保员工仅绑定指定角色（幂等）。"""
    existing = list(db.scalars(select(StaffRole).where(StaffRole.staff_id == staff.id)).all())
    for sr in existing:
        if sr.role_id != role.id:
            db.delete(sr)
    db.flush()
    linked = db.scalar(
        select(StaffRole).where(StaffRole.staff_id == staff.id, StaffRole.role_id == role.id)
    )
    if linked is None:
        db.add(StaffRole(staff_id=staff.id, role_id=role.id))
        db.flush()


def _ensure_member(
    db: Session,
    *,
    site_id: int,
    merchant_id: int,
    phone: str,
    name: str,
    referrer_member_id: int | None = None,
) -> Member:
    member = db.scalar(select(Member).where(Member.site_id == site_id, Member.phone == phone))
    if member is None:
        member = Member(
            site_id=site_id,
            phone=phone,
            name=name,
            face_status=FaceStatus.NOT_ENROLLED.value,
            referrer_member_id=referrer_member_id,
        )
        db.add(member)
        db.flush()
    elif referrer_member_id is not None and member.referrer_member_id is None:
        member.referrer_member_id = referrer_member_id
        db.flush()
    link = db.scalar(
        select(MerchantMember).where(
            MerchantMember.merchant_id == merchant_id,
            MerchantMember.member_id == member.id,
        )
    )
    if link is None:
        db.add(MerchantMember(merchant_id=merchant_id, member_id=member.id))
        db.flush()
    return member


def _ensure_point(
    db: Session,
    *,
    site_id: int,
    merchant_id: int | None,
    name: str,
    is_public_area: bool = False,
) -> AccessPoint:
    q = select(AccessPoint).where(AccessPoint.site_id == site_id, AccessPoint.name == name)
    point = db.scalar(q)
    if point is None:
        point = AccessPoint(
            site_id=site_id,
            merchant_id=merchant_id,
            name=name,
            is_public_area=is_public_area,
        )
        db.add(point)
        db.flush()
    return point


def _ensure_device(db: Session, *, access_point_id: int, device_code: str, api_key: str) -> AccessDevice:
    device = db.scalar(select(AccessDevice).where(AccessDevice.device_code == device_code))
    if device is None:
        device = AccessDevice(
            access_point_id=access_point_id,
            device_code=device_code,
            api_key_hash=hash_device_api_key(api_key),
            is_online=False,
        )
        db.add(device)
        db.flush()
    return device


def _ensure_product(
    db: Session,
    *,
    merchant_id: int,
    name: str,
    product_type: str,
    price: str,
    access_point_ids: list[int],
    duration_days: int | None = None,
    session_count: int | None = None,
    stored_value: str | None = None,
    is_trial: bool = False,
    promo_price: str | None = None,
) -> MembershipProduct:
    product = db.scalar(
        select(MembershipProduct).where(
            MembershipProduct.merchant_id == merchant_id,
            MembershipProduct.name == name,
        )
    )
    if product is None:
        now = _now()
        product = MembershipProduct(
            merchant_id=merchant_id,
            name=name,
            product_type=product_type,
            price=Decimal(price),
            duration_days=duration_days,
            session_count=session_count,
            stored_value=Decimal(stored_value) if stored_value is not None else None,
            is_trial=is_trial,
            promo_price=Decimal(promo_price) if promo_price else None,
            promo_starts_at=now - timedelta(days=1) if promo_price else None,
            promo_ends_at=now + timedelta(days=30) if promo_price else None,
            is_active=True,
        )
        db.add(product)
        db.flush()
        for ap_id in access_point_ids:
            exists = db.scalar(
                select(MembershipProductAccessPoint).where(
                    MembershipProductAccessPoint.product_id == product.id,
                    MembershipProductAccessPoint.access_point_id == ap_id,
                )
            )
            if exists is None:
                db.add(MembershipProductAccessPoint(product_id=product.id, access_point_id=ap_id))
        db.flush()
    return product


def _ensure_commission_rule(
    db: Session,
    *,
    merchant_id: int,
    name: str,
    scope: str,
    beneficiary: str,
    basis: str,
    rate: str | None = None,
    unit_amount: str | None = None,
    first_order_only: bool = False,
    priority: int = 100,
) -> CommissionRule:
    """按商户 + 规则名幂等写入提成规则。"""
    row = db.scalar(
        select(CommissionRule).where(
            CommissionRule.merchant_id == merchant_id,
            CommissionRule.name == name,
        )
    )
    if row is None:
        row = CommissionRule(
            merchant_id=merchant_id,
            name=name,
            scope=scope,
            beneficiary=beneficiary,
            basis=basis,
            rate=Decimal(rate) if rate is not None else None,
            unit_amount=Decimal(unit_amount) if unit_amount is not None else None,
            first_order_only=first_order_only,
            priority=priority,
            is_active=True,
        )
        db.add(row)
        db.flush()
    return row


def seed_demo_catalog(
    db: Session,
    *,
    site: Site,
    gym: Merchant,
    bar: Merchant | None,
    role_map: dict[str, Role],
) -> None:
    """写入交付级 Demo 目录数据。"""
    bar_type = db.scalar(select(MerchantType).where(MerchantType.code == "bar"))
    if bar is None and bar_type is not None:
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
    elif bar is not None:
        bar.name = "观野BAR"

    if bar is not None:
        from app.core.domain.subsystems import replace_merchant_subsystems
        from app.systems.platform.models.org import MerchantSubsystem
        from app.systems.platform.services.role_packs import ensure_merchant_role_packs

        if db.scalar(select(MerchantSubsystem).where(MerchantSubsystem.merchant_id == bar.id)) is None:
            replace_merchant_subsystems(db, bar.id, ["catering"])
        ensure_merchant_role_packs(db, bar.id)

    from app.systems.platform.services.role_packs import ensure_merchant_role_packs

    ensure_merchant_role_packs(db, gym.id)

    # —— 提成规则 ——
    rule_membership = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="会籍销售提成10%",
        scope=CommissionScope.MEMBERSHIP_SALE.value,
        beneficiary=CommissionBeneficiary.SELLER.value,
        basis=CommissionBasis.PERCENT.value,
        rate="0.10",
        priority=100,
    )
    rule_pt_sale = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="私教课包销售8%",
        scope=CommissionScope.PT_SALE.value,
        beneficiary=CommissionBeneficiary.SELLER.value,
        basis=CommissionBasis.PERCENT.value,
        rate="0.08",
        priority=110,
    )
    rule_retail = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="零售销售5%",
        scope=CommissionScope.RETAIL_SALE.value,
        beneficiary=CommissionBeneficiary.SELLER.value,
        basis=CommissionBasis.PERCENT.value,
        rate="0.05",
        priority=120,
    )
    rule_activity = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="活动报名固定20元",
        scope=CommissionScope.ACTIVITY_SALE.value,
        beneficiary=CommissionBeneficiary.SELLER.value,
        basis=CommissionBasis.FIXED.value,
        unit_amount="20.00",
        priority=130,
    )
    rule_group = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="团课按出席15元/人",
        scope=CommissionScope.GROUP_SESSION.value,
        beneficiary=CommissionBeneficiary.COACH.value,
        basis=CommissionBasis.PER_HEAD.value,
        unit_amount="15.00",
        priority=140,
    )
    rule_pt_session = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="私教课时60元/节",
        scope=CommissionScope.PT_SESSION.value,
        beneficiary=CommissionBeneficiary.COACH.value,
        basis=CommissionBasis.PER_SESSION.value,
        unit_amount="60.00",
        priority=150,
    )
    rule_referral = _ensure_commission_rule(
        db,
        merchant_id=gym.id,
        name="推荐成交首单50元",
        scope=CommissionScope.REFERRAL.value,
        beneficiary=CommissionBeneficiary.REFERRER.value,
        basis=CommissionBasis.FIXED.value,
        unit_amount="50.00",
        first_order_only=True,
        priority=160,
    )
    _ = (rule_pt_sale, rule_retail, rule_activity, rule_referral)

    def merchant_role(merchant_id: int, code: str) -> Role | None:
        return db.scalar(select(Role).where(Role.merchant_id == merchant_id, Role.code == code))

    # —— 场地级员工 ——
    if "site_ops" in role_map:
        site_ops = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=None,
            username="site_ops",
            password=DEMO_PASSWORD,
            display_name="综合运营·张敏",
            role=role_map["site_ops"],
        )
        _ensure_staff_role(db, site_ops, role_map["site_ops"])
    if "site_finance" in role_map:
        finance = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=None,
            username="finance",
            password=DEMO_PASSWORD,
            display_name="财务·李会计",
            role=role_map["site_finance"],
        )
        _ensure_staff_role(db, finance, role_map["site_finance"])

    # —— 健身房员工 ——
    gym_admin_role = merchant_role(gym.id, "gym_admin")
    gym_coach_role = merchant_role(gym.id, "gym_coach")
    gym_ops_role = merchant_role(gym.id, "gym_ops")
    gym_front_role = merchant_role(gym.id, "gym_front")
    gym_sales_role = merchant_role(gym.id, "gym_sales")

    gym_admin: StaffUser | None = None
    if gym_admin_role is not None:
        gym_admin = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=gym.id,
            username="gym_admin",
            password=DEMO_PASSWORD,
            display_name="陈店长",
            role=gym_admin_role,
        )
        _ensure_staff_role(db, gym_admin, gym_admin_role)

    coach_staff_1: StaffUser | None = None
    coach_staff_2: StaffUser | None = None
    if gym_coach_role is not None:
        coach_staff_1 = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=gym.id,
            username="coach01",
            password=DEMO_PASSWORD,
            display_name="教练·阿强",
            role=gym_coach_role,
        )
        _ensure_staff_role(db, coach_staff_1, gym_coach_role)
        coach_staff_2 = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=gym.id,
            username="coach02",
            password=DEMO_PASSWORD,
            display_name="教练·小雅",
            role=gym_coach_role,
        )
        _ensure_staff_role(db, coach_staff_2, gym_coach_role)

    if gym_ops_role is not None:
        gym_ops = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=gym.id,
            username="gym_ops",
            password=DEMO_PASSWORD,
            display_name="运营·小陈",
            role=gym_ops_role,
        )
        _ensure_staff_role(db, gym_ops, gym_ops_role)

    if gym_front_role is not None:
        front = _get_or_create_staff(
            db,
            site_id=site.id,
            merchant_id=gym.id,
            username="front01",
            password=DEMO_PASSWORD,
            display_name="前台·小王",
            role=gym_front_role,
        )
        _ensure_staff_role(db, front, gym_front_role)

    sales_staff: list[StaffUser] = []
    if gym_sales_role is not None:
        for username, display_name in (
            ("sales01", "销售·大明"),
            ("sales02", "销售·小芳"),
            ("sales03", "销售·小军"),
        ):
            staff = _get_or_create_staff(
                db,
                site_id=site.id,
                merchant_id=gym.id,
                username=username,
                password=DEMO_PASSWORD,
                display_name=display_name,
                role=gym_sales_role,
            )
            _ensure_staff_role(db, staff, gym_sales_role)
            sales_staff.append(staff)

    # —— 清吧员工 ——
    if bar is not None:
        bar_admin_role = merchant_role(bar.id, "bar_admin")
        bar_ops_role = merchant_role(bar.id, "bar_ops")
        bar_cashier_role = merchant_role(bar.id, "bar_cashier")
        if bar_admin_role is not None:
            bar_admin = _get_or_create_staff(
                db,
                site_id=site.id,
                merchant_id=bar.id,
                username="bar_admin",
                password=DEMO_PASSWORD,
                display_name="赵店长",
                role=bar_admin_role,
            )
            _ensure_staff_role(db, bar_admin, bar_admin_role)
        if bar_ops_role is not None:
            bar_ops = _get_or_create_staff(
                db,
                site_id=site.id,
                merchant_id=bar.id,
                username="bar_ops",
                password=DEMO_PASSWORD,
                display_name="运营·小周",
                role=bar_ops_role,
            )
            _ensure_staff_role(db, bar_ops, bar_ops_role)
        if bar_cashier_role is not None:
            bar_cashier = _get_or_create_staff(
                db,
                site_id=site.id,
                merchant_id=bar.id,
                username="bar_cashier",
                password=DEMO_PASSWORD,
                display_name="收银·小刘",
                role=bar_cashier_role,
            )
            _ensure_staff_role(db, bar_cashier, bar_cashier_role)

    # —— 门禁 ——
    main_door = _ensure_point(db, site_id=site.id, merchant_id=gym.id, name="健身房正门")
    side_door = _ensure_point(db, site_id=site.id, merchant_id=gym.id, name="健身房侧门")
    public_door = _ensure_point(
        db, site_id=site.id, merchant_id=None, name="园区公共门", is_public_area=True
    )
    _ensure_device(db, access_point_id=main_door.id, device_code="pad-gym-main", api_key="demo-pad-main")
    _ensure_device(db, access_point_id=side_door.id, device_code="pad-gym-side", api_key="demo-pad-side")
    _ensure_device(db, access_point_id=public_door.id, device_code="pad-site-gate", api_key="demo-pad-gate")
    gym_point_ids = [main_door.id, side_door.id]

    # —— 健身房会员（含推荐链） ——
    zhang_san = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001001", name="会员·张三"
    )
    li_si = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001002",
        name="会员·李四",
        referrer_member_id=zhang_san.id,
    )
    wang_wu = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001003",
        name="会员·王五",
        referrer_member_id=li_si.id,
    )
    zhao_liu = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001004",
        name="会员·赵六",
        referrer_member_id=zhang_san.id,
    )
    sun_qi = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001005",
        name="会员·孙七",
        referrer_member_id=zhang_san.id,
    )
    zhou_ba = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001006",
        name="会员·周八",
        referrer_member_id=zhao_liu.id,
    )
    wu_jiu = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001007", name="会员·吴九"
    )
    zheng_shi = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001008",
        name="会员·郑十",
        referrer_member_id=li_si.id,
    )
    qian_shiyi = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001009", name="会员·钱十一"
    )
    chen_shier = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001010", name="会员·陈十二"
    )
    gym_members = [
        zhang_san,
        li_si,
        wang_wu,
        zhao_liu,
        sun_qi,
        zhou_ba,
        wu_jiu,
        zheng_shi,
        qian_shiyi,
        chen_shier,
    ]

    if bar is not None:
        _ensure_member(db, site_id=site.id, merchant_id=bar.id, phone="13800001001", name="会员·张三")
        _ensure_member(db, site_id=site.id, merchant_id=bar.id, phone="13800002001", name="会员·林夜")

    for member in gym_members:
        ensure_member_promoter_code(db, member, force=False)

    # —— 会籍卡种 ——
    _ensure_product(
        db,
        merchant_id=gym.id,
        name="体验周卡",
        product_type=ProductType.TERM.value,
        price="39.00",
        duration_days=7,
        access_point_ids=gym_point_ids,
        is_trial=True,
        promo_price="19.00",
    )
    _ensure_product(
        db,
        merchant_id=gym.id,
        name="标准月卡",
        product_type=ProductType.TERM.value,
        price="299.00",
        duration_days=30,
        access_point_ids=gym_point_ids,
    )
    _ensure_product(
        db,
        merchant_id=gym.id,
        name="季卡",
        product_type=ProductType.TERM.value,
        price="799.00",
        duration_days=90,
        access_point_ids=gym_point_ids,
        promo_price="699.00",
    )
    _ensure_product(
        db,
        merchant_id=gym.id,
        name="次卡10次",
        product_type=ProductType.COUNT.value,
        price="399.00",
        session_count=10,
        access_point_ids=gym_point_ids,
    )
    _ensure_product(
        db,
        merchant_id=gym.id,
        name="储值卡500",
        product_type=ProductType.VALUE.value,
        price="500.00",
        stored_value="500.00",
        access_point_ids=gym_point_ids,
    )

    # —— 员工关联会员（MERCHANT 来源，独立手机号） ——
    def ensure_staff_member(phone: str, name: str) -> Member:
        member = db.scalar(select(Member).where(Member.site_id == site.id, Member.phone == phone))
        if member is None:
            member = Member(
                site_id=site.id,
                phone=phone,
                name=name,
                face_status=FaceStatus.NOT_ENROLLED.value,
                acquisition_source=AcquisitionSource.MERCHANT.value,
                first_merchant_id=gym.id,
            )
            db.add(member)
            db.flush()
        linked = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == member.id,
                MerchantMember.merchant_id == gym.id,
            )
        )
        if linked is None:
            db.add(MerchantMember(member_id=member.id, merchant_id=gym.id))
            db.flush()
        ensure_member_promoter_code(db, member, force=True)
        return member

    def ensure_coach(staff: StaffUser, display_name: str, specialties: str, *, phone: str) -> Coach:
        member = ensure_staff_member(phone, display_name)
        coach = db.scalar(select(Coach).where(Coach.staff_user_id == staff.id))
        if coach is None:
            coach = Coach(
                merchant_id=gym.id,
                staff_user_id=staff.id,
                member_id=member.id,
                display_name=display_name,
                specialties=specialties,
                availability_note="工作日 10:00-21:00",
                is_active=True,
            )
            db.add(coach)
            db.flush()
        else:
            coach.member_id = member.id
            coach.display_name = display_name
        return coach

    coach_qiang: Coach | None = None
    coach_ya: Coach | None = None
    if coach_staff_1 is not None:
        coach_qiang = ensure_coach(coach_staff_1, "教练·阿强", "增肌,力量", phone="13910001001")
        coach_qiang.title = "金牌私教"
        coach_qiang.gender = "male"
        coach_qiang.years_experience = 8
        coach_qiang.bio = "力量训练与增肌方向，带过多名备赛学员。"
        coach_qiang.group_commission_rule_id = rule_group.id
        coach_qiang.pt_commission_rule_id = rule_pt_session.id
    if coach_staff_2 is not None:
        coach_ya = ensure_coach(coach_staff_2, "教练·小雅", "减脂,团操", phone="13910001002")
        coach_ya.title = "团课主教练"
        coach_ya.gender = "female"
        coach_ya.years_experience = 6
        coach_ya.bio = "减脂塑形与团操，课堂氛围活泼。"
        coach_ya.group_commission_rule_id = rule_group.id
        coach_ya.pt_commission_rule_id = rule_pt_session.id

    # —— 销售档案（仅 sales01/02/03） ——
    sales_phone_map = {
        "sales01": ("13910001011", "销售·大明"),
        "sales02": ("13910001012", "销售·小芳"),
        "sales03": ("13910001013", "销售·小军"),
    }

    def ensure_sales_rep(staff: StaffUser) -> SalesRep | None:
        phone, display_name = sales_phone_map.get(staff.username, (None, staff.display_name))
        if phone is None:
            return None
        member = ensure_staff_member(phone, display_name)
        rep = db.scalar(select(SalesRep).where(SalesRep.staff_user_id == staff.id))
        if rep is None:
            rep = SalesRep(
                merchant_id=gym.id,
                staff_user_id=staff.id,
                member_id=member.id,
                display_name=display_name,
                commission_rule_id=rule_membership.id,
                is_active=True,
            )
            db.add(rep)
            db.flush()
        else:
            rep.commission_rule_id = rule_membership.id
            rep.display_name = display_name
        link_sales_member(
            db, sales_rep=rep, site_id=site.id, merchant_id=gym.id, member_id=member.id
        )
        return rep

    for staff in sales_staff:
        ensure_sales_rep(staff)

    # —— 私教课包 ——
    pt = db.scalar(
        select(PtPackageProduct).where(
            PtPackageProduct.merchant_id == gym.id,
            PtPackageProduct.name == "私教10节",
        )
    )
    if pt is None:
        pt = PtPackageProduct(
            merchant_id=gym.id,
            name="私教10节",
            price=Decimal("2980.00"),
            session_count=10,
            valid_days=90,
            all_coaches=True,
            promo_price=Decimal("2680.00"),
            promo_starts_at=_now() - timedelta(days=1),
            promo_ends_at=_now() + timedelta(days=30),
            is_active=True,
        )
        db.add(pt)
        db.flush()
    pt20 = db.scalar(
        select(PtPackageProduct).where(
            PtPackageProduct.merchant_id == gym.id,
            PtPackageProduct.name == "私教20节",
        )
    )
    if pt20 is None:
        db.add(
            PtPackageProduct(
                merchant_id=gym.id,
                name="私教20节",
                price=Decimal("5280.00"),
                session_count=20,
                valid_days=180,
                all_coaches=True,
                is_active=True,
            )
        )
        db.flush()

    # —— 团课与近几天排课 ——
    course = db.scalar(
        select(GroupCourse).where(GroupCourse.merchant_id == gym.id, GroupCourse.name == "燃脂操")
    )
    if course is None:
        course = GroupCourse(
            merchant_id=gym.id,
            name="燃脂操",
            difficulty="中级",
            default_duration_minutes=55,
            default_capacity=20,
            book_ahead_minutes=60,
            cancel_ahead_minutes=120,
            is_active=True,
        )
        db.add(course)
        db.flush()
    yoga = db.scalar(
        select(GroupCourse).where(GroupCourse.merchant_id == gym.id, GroupCourse.name == "晨间瑜伽")
    )
    if yoga is None:
        yoga = GroupCourse(
            merchant_id=gym.id,
            name="晨间瑜伽",
            difficulty="初级",
            default_duration_minutes=60,
            default_capacity=15,
            book_ahead_minutes=30,
            cancel_ahead_minutes=60,
            is_active=True,
        )
        db.add(yoga)
        db.flush()

    def ensure_session(c: GroupCourse, coach: Coach, start: datetime, room: str) -> None:
        exists = db.scalar(
            select(GroupSession).where(
                GroupSession.course_id == c.id,
                GroupSession.starts_at == start,
            )
        )
        if exists is None:
            db.add(
                GroupSession(
                    merchant_id=gym.id,
                    course_id=c.id,
                    coach_id=coach.id,
                    starts_at=start,
                    ends_at=start + timedelta(minutes=c.default_duration_minutes),
                    room=room,
                    capacity=c.default_capacity,
                    status=GroupSessionStatus.OPEN.value,
                )
            )

    if coach_qiang is not None and coach_ya is not None:
        tomorrow = (_now() + timedelta(days=1)).replace(hour=19, minute=0, second=0, microsecond=0)
        day_after = (_now() + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
        ensure_session(course, coach_ya, tomorrow, "团操房 A")
        ensure_session(yoga, coach_ya, day_after, "团操房 B")
        ensure_session(course, coach_qiang, day_after.replace(hour=19), "团操房 A")
        db.flush()

    # —— 零售 ——
    cat = db.scalar(
        select(ProductCategory).where(
            ProductCategory.merchant_id == gym.id,
            ProductCategory.name == "运动补给",
        )
    )
    if cat is None:
        cat = ProductCategory(merchant_id=gym.id, name="运动补给", sort_order=1, is_active=True)
        db.add(cat)
        db.flush()
    drink_cat = db.scalar(
        select(ProductCategory).where(
            ProductCategory.merchant_id == gym.id,
            ProductCategory.name == "饮品",
        )
    )
    if drink_cat is None:
        drink_cat = ProductCategory(merchant_id=gym.id, name="饮品", sort_order=2, is_active=True)
        db.add(drink_cat)
        db.flush()

    def ensure_sku(
        *,
        category_id: int,
        name: str,
        price: str,
        stock: int,
        unit: str = "件",
        barcode: str | None = None,
    ) -> RetailSku:
        sku = db.scalar(
            select(RetailSku).where(RetailSku.merchant_id == gym.id, RetailSku.name == name)
        )
        if sku is None:
            sku = RetailSku(
                merchant_id=gym.id,
                category_id=category_id,
                name=name,
                price=Decimal(price),
                unit=unit,
                barcode=barcode,
                stock_qty=stock,
                low_stock_threshold=5,
                is_active=True,
            )
            db.add(sku)
            db.flush()
            if stock > 0 and gym_admin is not None:
                db.add(
                    StockMovement(
                        merchant_id=gym.id,
                        sku_id=sku.id,
                        movement_type=StockMovementType.IN.value,
                        quantity_delta=stock,
                        stock_after=stock,
                        note="Demo 初始入库",
                        actor_staff_id=gym_admin.id,
                    )
                )
                db.flush()
        return sku

    ensure_sku(category_id=cat.id, name="乳清蛋白粉 1kg", price="268.00", stock=20, barcode="DEMO-PROTEIN-1")
    ensure_sku(category_id=cat.id, name="能量棒", price="18.00", stock=50, barcode="DEMO-BAR-1")
    ensure_sku(category_id=drink_cat.id, name="电解质水", price="8.00", stock=80, barcode="DEMO-WATER-1")
    ensure_sku(category_id=drink_cat.id, name="即饮蛋白奶", price="22.00", stock=30, barcode="DEMO-SHAKE-1")

    # —— 优惠券 ——
    coupon = db.scalar(
        select(CouponTemplate).where(
            CouponTemplate.merchant_id == gym.id,
            CouponTemplate.name == "新客满200减30",
        )
    )
    if coupon is None:
        now = _now()
        db.add(
            CouponTemplate(
                merchant_id=gym.id,
                name="新客满200减30",
                discount_type=DiscountType.FIXED.value,
                threshold_amount=Decimal("200.00"),
                fixed_amount=Decimal("30.00"),
                percent_off=None,
                applicable_to=ApplicableTo.BOTH.value,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=60),
                total_limit=500,
                issued_count=0,
                claimable=True,
                per_member_limit=1,
                is_active=True,
            )
        )
        db.flush()
    pct = db.scalar(
        select(CouponTemplate).where(
            CouponTemplate.merchant_id == gym.id,
            CouponTemplate.name == "会籍9折券",
        )
    )
    if pct is None:
        now = _now()
        db.add(
            CouponTemplate(
                merchant_id=gym.id,
                name="会籍9折券",
                discount_type=DiscountType.PERCENT.value,
                threshold_amount=Decimal("0"),
                fixed_amount=None,
                percent_off=10,
                applicable_to=ApplicableTo.MEMBERSHIP.value,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=30),
                total_limit=100,
                issued_count=0,
                claimable=True,
                per_member_limit=1,
                is_active=True,
            )
        )
        db.flush()

    # —— 器材 ——
    def ensure_asset(code: str, name: str, category: str, area: str) -> None:
        asset = db.scalar(
            select(EquipmentAsset).where(
                EquipmentAsset.merchant_id == gym.id,
                EquipmentAsset.asset_code == code,
            )
        )
        if asset is None:
            db.add(
                EquipmentAsset(
                    merchant_id=gym.id,
                    name=name,
                    category=category,
                    brand_model="Demo Brand",
                    asset_code=code,
                    area=area,
                    status=EquipmentStatus.IN_USE.value,
                    note="Demo 台账",
                )
            )

    ensure_asset("EQ-TM-001", "跑步机 A1", "cardio", "有氧区")
    ensure_asset("EQ-TM-002", "跑步机 A2", "cardio", "有氧区")
    ensure_asset("EQ-DB-001", "哑铃架", "strength", "力量区")
    ensure_asset("EQ-SG-001", "史密斯机", "strength", "力量区")
    db.flush()

    # —— 活动 ——
    demo_activity = db.scalar(
        select(Activity).where(Activity.merchant_id == gym.id, Activity.name == "夏季体测")
    )
    if demo_activity is None:
        starts = _now() + timedelta(days=10)
        db.add(
            Activity(
                merchant_id=gym.id,
                name="夏季体测",
                category="赛事",
                location="多功能厅",
                description="体脂、力量与有氧指标检测。发布后会员可在观野FIT 首页与活动页报名。",
                starts_at=starts,
                ends_at=starts + timedelta(days=1),
                register_ends_at=starts - timedelta(days=1),
                capacity=50,
                price=Decimal("0"),
                requires_payment=False,
                status=ActivityStatus.PUBLISHED.value,
            )
        )
        db.flush()

    # —— 清吧菜单 ——
    if bar is not None:
        def ensure_menu_category(name: str, sort_order: int) -> CateringMenuCategory:
            row = db.scalar(
                select(CateringMenuCategory).where(
                    CateringMenuCategory.merchant_id == bar.id,
                    CateringMenuCategory.name == name,
                )
            )
            if row is None:
                row = CateringMenuCategory(
                    merchant_id=bar.id,
                    name=name,
                    sort_order=sort_order,
                    is_active=True,
                )
                db.add(row)
                db.flush()
            return row

        demo_cats = {
            "饮品": ensure_menu_category("饮品", 10),
            "鸡尾酒": ensure_menu_category("鸡尾酒", 20),
            "酒水": ensure_menu_category("酒水", 30),
            "小食": ensure_menu_category("小食", 40),
        }
        for name, category, price, description in (
            ("特调气泡水", "饮品", "28.00", "苏打气泡底，清爽微甜，适合佐餐或解腻。"),
            ("美式咖啡", "饮品", "22.00", "深烘浓缩拉热美式，可做冰饮。"),
            ("经典莫吉托", "鸡尾酒", "48.00", "朗姆、青柠与薄荷，冰镇后口感清爽。"),
            ("精酿啤酒", "酒水", "38.00", "店内精选生啤，酒花香气明显。"),
            ("炸薯条", "小食", "22.00", "外脆里软，可配番茄酱或蒜香黄油。"),
            ("香辣鸡翅", "小食", "32.00", "现炸鸡翅，微辣，配甜辣酱。"),
        ):
            exists = db.scalar(
                select(CateringMenuItem).where(
                    CateringMenuItem.merchant_id == bar.id,
                    CateringMenuItem.name == name,
                )
            )
            cat = demo_cats[category]
            if exists is None:
                db.add(
                    CateringMenuItem(
                        merchant_id=bar.id,
                        name=name,
                        category_id=cat.id,
                        category=cat.name,
                        price=Decimal(price),
                        description=description,
                        is_active=True,
                    )
                )
            else:
                exists.category_id = cat.id
                exists.category = cat.name
                if not exists.description:
                    exists.description = description
        db.flush()

        dining_tpl = db.scalar(
            select(CouponTemplate).where(
                CouponTemplate.merchant_id == bar.id,
                CouponTemplate.name == "满20减5",
            )
        )
        if dining_tpl is None:
            now = _now()
            dining_tpl = CouponTemplate(
                merchant_id=bar.id,
                name="满20减5",
                discount_type=DiscountType.FIXED.value,
                threshold_amount=Decimal("20.00"),
                fixed_amount=Decimal("5.00"),
                percent_off=None,
                applicable_to=ApplicableTo.DINING.value,
                starts_at=now - timedelta(days=1),
                ends_at=now + timedelta(days=60),
                total_limit=500,
                issued_count=0,
                claimable=True,
                per_member_limit=1,
                is_active=True,
            )
            db.add(dining_tpl)
            db.flush()
        owned = db.scalar(
            select(MemberCoupon).where(
                MemberCoupon.member_id == zhang_san.id,
                MemberCoupon.template_id == dining_tpl.id,
            )
        )
        if owned is None:
            db.add(
                MemberCoupon(
                    merchant_id=bar.id,
                    template_id=dining_tpl.id,
                    member_id=zhang_san.id,
                    status=MemberCouponStatus.UNUSED.value,
                    starts_at=dining_tpl.starts_at,
                    ends_at=dining_tpl.ends_at,
                )
            )
            dining_tpl.issued_count = int(dining_tpl.issued_count or 0) + 1
            db.flush()

        for idx, table_name in enumerate(["吧台", "A1", "A2", "A3", "B1", "卡座1", "卡座2"]):
            table = db.scalar(
                select(CateringTable).where(
                    CateringTable.merchant_id == bar.id,
                    CateringTable.name == table_name,
                )
            )
            if table is None:
                db.add(
                    CateringTable(
                        merchant_id=bar.id,
                        name=table_name,
                        code=generate_table_code(db),
                        sort_order=(idx + 1) * 10,
                        is_active=True,
                    )
                )
                db.flush()

    def _ensure_agreement(merchant: Merchant, scene: str, title: str, content: str) -> None:
        row = db.scalar(
            select(LegalAgreement).where(
                LegalAgreement.merchant_id == merchant.id,
                LegalAgreement.scene == scene,
            )
        )
        if row is None:
            db.add(
                LegalAgreement(
                    site_id=site.id,
                    merchant_id=merchant.id,
                    scene=scene,
                    title=title,
                    content=content,
                    is_enabled=True,
                )
            )
            db.flush()

    _ensure_agreement(
        gym,
        "membership",
        "观野FIT会籍服务协议",
        "购买会籍即表示您已阅读并同意场馆守则、有效期与退款规则。请按预约到店，遵守器械使用规范。",
    )
    _ensure_agreement(
        gym,
        "pt_package",
        "观野FIT私教课包协议",
        "课包按次核销，逾期未约视为放弃剩余课时。改约请提前与教练沟通。",
    )
    _ensure_agreement(
        gym,
        "activity",
        "观野FIT活动报名须知",
        "报名成功即占用名额。无故缺席可能影响后续活动报名。收费活动退款规则以活动说明为准。",
    )
    if bar is not None:
        _ensure_agreement(
            bar,
            "dining",
            "观野BAR点餐须知",
            "下单后厨房按桌出餐。如需退款请联系吧台。酒水请适量饮用，未成年人禁止饮酒。",
        )

    # —— 站内通知 ——
    notice_title = "【Demo】欢迎体验综合场地管理系统"
    exists_notice = db.scalar(
        select(Notification).where(
            Notification.site_id == site.id,
            Notification.title == notice_title,
        )
    )
    if exists_notice is None:
        db.add(
            Notification(
                site_id=site.id,
                merchant_id=gym.id,
                member_id=None,
                audience="staff",
                event_type="demo.welcome",
                title=notice_title,
                body="已预置会员、卡种、教练、销售、团课、零售与优惠券等目录数据，可直接在各菜单体验。",
            )
        )
        db.add(
            Notification(
                site_id=site.id,
                merchant_id=gym.id,
                member_id=zhang_san.id,
                audience="member",
                event_type="demo.welcome",
                title="【Demo】会员端欢迎通知",
                body="可用手机号 13800001001 登录会员 H5，验证码见 MEMBER_OTP_MOCK_CODE（默认 123456）。",
            )
        )
        db.flush()
