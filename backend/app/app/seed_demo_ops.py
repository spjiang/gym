"""Demo 运营样本：场地政策、会员网络、样例订单与履约数据。

幂等：按【Demo】标记或业务唯一键跳过已存在记录。
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.systems.gym.models.membership import (
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipProduct,
)
from app.systems.gym.models.retail import RetailOrderItem, RetailOrderLink, RetailSku
from app.systems.gym.services.commission import accrue_order_commissions
from app.systems.gym.services.coupon import redeem_coupon_for_order
from app.systems.gym.services.fulfillment import (
    fulfill_membership_order,
    product_access_point_ids,
    validate_product_for_sale,
)
from app.systems.gym.services.pricing import effective_price
from app.systems.gym.services.pt_fulfillment import fulfill_pt_package_order
from app.systems.gym.services.retail_fulfillment import assert_retail_stock_available, fulfill_retail_order
from app.systems.gym.services.activity_fulfillment import fulfill_activity_order
from app.systems.gym.services.commission_policy import get_or_create_settings as get_commission_settings
from app.systems.platform.models.commerce import Order, OrderStatus, Payment, PaymentChannel, PaymentKind
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant, Site
from app.systems.platform.services.order_pricing import price_order
from app.systems.platform.services.promotion import ensure_member_promoter_code, get_or_create_settings_row

UTC = timezone.utc
DEMO_TAG = "【Demo】"


def _now() -> datetime:
    return datetime.now(UTC)


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
    else:
        member.name = name
        if referrer_member_id is not None and member.referrer_member_id is None:
            member.referrer_member_id = referrer_member_id
    link = db.scalar(
        select(MerchantMember).where(
            MerchantMember.merchant_id == merchant_id,
            MerchantMember.member_id == member.id,
        )
    )
    if link is None:
        db.add(MerchantMember(merchant_id=merchant_id, member_id=member.id))
        db.flush()
    ensure_member_promoter_code(db, member, force=True)
    return member


def _seed_site_policies(db: Session, site: Site) -> None:
    """场地级推广与提成结算政策。"""
    promo = get_or_create_settings_row(db, site.id)
    promo.auto_create_member_code = True
    promo.default_rebate_rate = Decimal("0.05")
    promo.default_downline_discount_rate = Decimal("0.03")
    promo.min_withdraw_amount = Decimal("1.00")
    promo.withdraw_hold_days = 0
    promo.remark = "Demo 默认：返点 5%、下级 97 折、满 1 元可提现"

    comm = get_commission_settings(db, site.id)
    comm.settle_hold_days = 7
    comm.remark = "Demo 默认：计提后 7 天可结算"
    db.flush()


def _seed_member_network(db: Session, *, site: Site, gym: Merchant, bar: Merchant | None) -> dict[str, Member]:
    """会员裂变链 + 扩展样本会员。"""
    zhang = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001001", name="会员·张三"
    )
    li = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001002",
        name="会员·李四",
        referrer_member_id=zhang.id,
    )
    wang = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001003",
        name="会员·王五",
        referrer_member_id=li.id,
    )
    zhao = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001004",
        name="会员·赵六",
        referrer_member_id=zhang.id,
    )
    sun = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001005",
        name="会员·孙七",
        referrer_member_id=zhang.id,
    )
    zhou = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001006",
        name="会员·周八",
        referrer_member_id=zhao.id,
    )
    wu = _ensure_member(
        db, site_id=site.id, merchant_id=gym.id, phone="13800001007", name="会员·吴九"
    )
    zheng = _ensure_member(
        db,
        site_id=site.id,
        merchant_id=gym.id,
        phone="13800001008",
        name="会员·郑十",
        referrer_member_id=li.id,
    )
    if bar is not None:
        _ensure_member(db, site_id=site.id, merchant_id=bar.id, phone="13800001001", name="会员·张三")
        _ensure_member(
            db,
            site_id=site.id,
            merchant_id=bar.id,
            phone="13800002001",
            name="会员·林夜",
        )
    db.flush()
    return {
        "zhang": zhang,
        "li": li,
        "wang": wang,
        "zhao": zhao,
        "sun": sun,
        "zhou": zhou,
        "wu": wu,
        "zheng": zheng,
    }


def _staff_id(db: Session, username: str) -> int | None:
    staff = db.scalar(select(StaffUser).where(StaffUser.username == username))
    return staff.id if staff else None


def _demo_order_exists(db: Session, *, merchant_id: int, title: str) -> bool:
    return (
        db.scalar(
            select(Order.id).where(Order.merchant_id == merchant_id, Order.title == title).limit(1)
        )
        is not None
    )


def _pay_demo_order(
    db: Session,
    order: Order,
    *,
    seller_staff_id: int | None,
    actor_staff_id: int | None,
) -> None:
    """模拟线下收款并走完整履约/提成/返点链路。"""
    if order.status == OrderStatus.PAID.value:
        return
    assert_retail_stock_available(db, order)
    order.status = OrderStatus.PAID.value
    if seller_staff_id is not None:
        order.seller_staff_id = seller_staff_id
    from app.systems.catering.services.kitchen import start_dining_kitchen

    start_dining_kitchen(order)
    db.add(
        Payment(
            order_id=order.id,
            kind=PaymentKind.CHARGE.value,
            channel=PaymentChannel.OFFLINE_CASH.value,
            amount=order.amount,
            note="Demo 线下收款",
        )
    )
    fulfill_membership_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_pt_package_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_retail_order(db, order, actor_staff_id=actor_staff_id)
    fulfill_activity_order(db, order, actor_staff_id=actor_staff_id)
    redeem_coupon_for_order(db, order, actor_staff_id=actor_staff_id)
    accrue_order_commissions(db, order)
    db.flush()


def _seed_membership_sample(
    db: Session,
    *,
    site: Site,
    gym: Merchant,
    member: Member,
    product_name: str,
    demo_title: str,
    seller_staff_id: int | None,
    actor_staff_id: int | None,
) -> None:
    if _demo_order_exists(db, merchant_id=gym.id, title=demo_title):
        return
    product = db.scalar(
        select(MembershipProduct).where(
            MembershipProduct.merchant_id == gym.id,
            MembershipProduct.name == product_name,
        )
    )
    if product is None:
        return
    ap_ids = product_access_point_ids(db, product.id)
    validate_product_for_sale(product, ap_ids)
    price = effective_price(product.price, product.promo_price, product.promo_starts_at, product.promo_ends_at)
    order = Order(
        site_id=site.id,
        merchant_id=gym.id,
        member_id=member.id,
        order_type="membership",
        title=demo_title,
        amount=price,
        status=OrderStatus.PENDING.value,
        seller_staff_id=seller_staff_id,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=price, member_coupon_id=None)
    db.add(
        MembershipOrderLink(
            order_id=order.id,
            member_id=member.id,
            product_id=product.id,
            action=MembershipOrderAction.PURCHASE.value,
        )
    )
    db.flush()
    _pay_demo_order(db, order, seller_staff_id=seller_staff_id, actor_staff_id=actor_staff_id)


def _seed_retail_sample(
    db: Session,
    *,
    site: Site,
    gym: Merchant,
    member: Member,
    sku_name: str,
    quantity: int,
    demo_title: str,
    seller_staff_id: int | None,
    actor_staff_id: int | None,
) -> None:
    if _demo_order_exists(db, merchant_id=gym.id, title=demo_title):
        return
    sku = db.scalar(
        select(RetailSku).where(RetailSku.merchant_id == gym.id, RetailSku.name == sku_name)
    )
    if sku is None or sku.stock_qty < quantity:
        return
    price = effective_price(sku.price, sku.promo_price, sku.promo_starts_at, sku.promo_ends_at)
    total = price * quantity
    order = Order(
        site_id=site.id,
        merchant_id=gym.id,
        member_id=member.id,
        order_type="retail",
        title=demo_title,
        amount=total,
        status=OrderStatus.PENDING.value,
        seller_staff_id=seller_staff_id,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=total, member_coupon_id=None)
    link = RetailOrderLink(order_id=order.id, member_id=member.id, fulfilled=False)
    db.add(link)
    db.flush()
    db.add(
        RetailOrderItem(
            order_link_id=link.id,
            sku_id=sku.id,
            quantity=quantity,
            unit_price=price,
        )
    )
    db.flush()
    _pay_demo_order(db, order, seller_staff_id=seller_staff_id, actor_staff_id=actor_staff_id)


def _seed_catering_sample(
    db: Session,
    *,
    site: Site,
    bar: Merchant,
    member: Member,
    demo_title: str,
    amount: str,
    seller_staff_id: int | None,
    actor_staff_id: int | None,
) -> None:
    if _demo_order_exists(db, merchant_id=bar.id, title=demo_title):
        return
    order = Order(
        site_id=site.id,
        merchant_id=bar.id,
        member_id=member.id,
        order_type="dining",
        title=demo_title,
        amount=Decimal(amount),
        status=OrderStatus.PENDING.value,
        seller_staff_id=seller_staff_id,
    )
    db.add(order)
    db.flush()
    price_order(db, order=order, original_amount=Decimal(amount), member_coupon_id=None)
    _pay_demo_order(db, order, seller_staff_id=seller_staff_id, actor_staff_id=actor_staff_id)


def seed_demo_operations(
    db: Session,
    *,
    site: Site,
    gym: Merchant,
    bar: Merchant | None,
) -> None:
    """写入行业标准 Demo 运营样本（政策 + 会员 + 样例流水）。"""
    _seed_site_policies(db, site)
    members = _seed_member_network(db, site=site, gym=gym, bar=bar)

    seller_id = _staff_id(db, "sales01") or _staff_id(db, "gym_admin")
    actor_id = seller_id or _staff_id(db, "admin")

    _seed_membership_sample(
        db,
        site=site,
        gym=gym,
        member=members["li"],
        product_name="标准月卡",
        demo_title=f"{DEMO_TAG}李四办标准月卡",
        seller_staff_id=_staff_id(db, "sales01"),
        actor_staff_id=actor_id,
    )
    _seed_membership_sample(
        db,
        site=site,
        gym=gym,
        member=members["wang"],
        product_name="体验周卡",
        demo_title=f"{DEMO_TAG}王五办体验周卡",
        seller_staff_id=_staff_id(db, "sales02"),
        actor_staff_id=actor_id,
    )
    _seed_retail_sample(
        db,
        site=site,
        gym=gym,
        member=members["zhao"],
        sku_name="电解质水",
        quantity=2,
        demo_title=f"{DEMO_TAG}赵六购买电解质水",
        seller_staff_id=_staff_id(db, "sales01"),
        actor_staff_id=actor_id,
    )
    _seed_retail_sample(
        db,
        site=site,
        gym=gym,
        member=members["wu"],
        sku_name="能量棒",
        quantity=3,
        demo_title=f"{DEMO_TAG}吴九购买能量棒",
        seller_staff_id=_staff_id(db, "sales03"),
        actor_staff_id=actor_id,
    )
    if bar is not None:
        bar_member = db.scalar(
            select(Member).where(Member.site_id == site.id, Member.phone == "13800001001")
        )
        if bar_member is not None:
            bar_seller = _staff_id(db, "bar_cashier") or _staff_id(db, "bar_admin")
            _seed_catering_sample(
                db,
                site=site,
                bar=bar,
                member=bar_member,
                demo_title=f"{DEMO_TAG}张三清吧消费",
                amount="76.00",
                seller_staff_id=bar_seller,
                actor_staff_id=bar_seller or actor_id,
            )
