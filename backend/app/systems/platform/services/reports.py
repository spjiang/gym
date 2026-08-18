"""经营报表：支付流水汇总与会籍/课程/库存看板。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.commerce import Order, Payment, PaymentKind
from app.systems.gym.models.activity import (
    OCCUPYING_REGISTRATION_STATUS,
    Activity,
    ActivityRegistration,
    RegistrationStatus,
)
from app.systems.gym.models.appointment import PtAppointment, PtAppointmentStatus
from app.systems.gym.models.course import (
    GroupBooking,
    GroupBookingStatus,
    GroupSession,
    GroupSessionStatus,
)
from app.systems.gym.models.membership import (
    Membership,
    MembershipOrderAction,
    MembershipOrderLink,
    MembershipStatus,
)
from app.systems.platform.models.org import Merchant
from app.systems.gym.models.retail import RetailSku, StockMovement, StockMovementType


def _money(value: Decimal | int | None) -> Decimal:
    """金额统一保留两位小数，避免报表出现 0 与 0.00 混排。"""
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _day_bounds(date_from: date, date_to: date) -> tuple[datetime, datetime]:
    """按 UTC 日界：含起止日全天。"""
    start = datetime.combine(date_from, time.min, tzinfo=timezone.utc)
    end = datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
    return start, end


def _base_query(
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> Select:
    start, end = _day_bounds(date_from, date_to)
    q = (
        select(Payment, Order)
        .join(Order, Order.id == Payment.order_id)
        .where(
            Order.site_id == site_id,
            Payment.created_at >= start,
            Payment.created_at < end,
        )
    )
    if merchant_id is not None:
        q = q.where(Order.merchant_id == merchant_id)
    return q.order_by(Payment.id.asc())


@dataclass
class CommerceSummary:
    charge_total: Decimal
    refund_total: Decimal
    net_total: Decimal
    by_channel: list[dict]
    by_order_type: list[dict]


def summarize_commerce(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> CommerceSummary:
    rows = db.execute(
        _base_query(site_id=site_id, date_from=date_from, date_to=date_to, merchant_id=merchant_id)
    ).all()

    charge = Decimal("0")
    refund = Decimal("0")
    channel_map: dict[str, dict[str, Decimal]] = {}
    type_map: dict[str, dict[str, Decimal]] = {}

    def _bump(bucket: dict[str, dict[str, Decimal]], key: str, kind: str, amount: Decimal) -> None:
        if key not in bucket:
            bucket[key] = {"charge": Decimal("0"), "refund": Decimal("0")}
        if kind == PaymentKind.CHARGE.value:
            bucket[key]["charge"] += amount
        elif kind == PaymentKind.REFUND.value:
            bucket[key]["refund"] += amount

    for payment, order in rows:
        amt = Decimal(payment.amount)
        if payment.kind == PaymentKind.CHARGE.value:
            charge += amt
        elif payment.kind == PaymentKind.REFUND.value:
            refund += amt
        _bump(channel_map, payment.channel, payment.kind, amt)
        _bump(type_map, order.order_type, payment.kind, amt)

    def _rows(bucket: dict[str, dict[str, Decimal]], key_name: str) -> list[dict]:
        out = []
        for key, vals in sorted(bucket.items()):
            out.append(
                {
                    key_name: key,
                    "charge_total": vals["charge"],
                    "refund_total": vals["refund"],
                    "net_total": vals["charge"] - vals["refund"],
                }
            )
        return out

    return CommerceSummary(
        charge_total=charge,
        refund_total=refund,
        net_total=charge - refund,
        by_channel=_rows(channel_map, "channel"),
        by_order_type=_rows(type_map, "order_type"),
    )


def list_commerce_payments(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> list[tuple[Payment, Order]]:
    return list(
        db.execute(
            _base_query(site_id=site_id, date_from=date_from, date_to=date_to, merchant_id=merchant_id)
        ).all()
    )


def _merchant_ids_for_site(db: Session, site_id: int, merchant_id: int | None) -> list[int] | None:
    """指定商户返回单元素列表；未指定返回场地全部商户 id。"""
    if merchant_id is not None:
        return [merchant_id]
    return list(db.scalars(select(Merchant.id).where(Merchant.site_id == site_id)).all())


@dataclass
class MembershipSummary:
    new_count: int
    renew_count: int
    active_count: int
    frozen_count: int
    expired_in_range: int


def summarize_membership(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> MembershipSummary:
    start, end = _day_bounds(date_from, date_to)
    mids = _merchant_ids_for_site(db, site_id, merchant_id)
    if not mids:
        return MembershipSummary(0, 0, 0, 0, 0)

    links = list(
        db.scalars(
            select(MembershipOrderLink)
            .join(Order, Order.id == MembershipOrderLink.order_id)
            .where(
                Order.site_id == site_id,
                Order.merchant_id.in_(mids),
                MembershipOrderLink.fulfilled_membership_id.is_not(None),
                MembershipOrderLink.created_at >= start,
                MembershipOrderLink.created_at < end,
            )
        ).all()
    )
    new_count = sum(1 for x in links if x.action == MembershipOrderAction.PURCHASE.value)
    renew_count = sum(1 for x in links if x.action == MembershipOrderAction.RENEW.value)

    memberships = list(
        db.scalars(
            select(Membership).where(
                Membership.merchant_id.in_(mids),
                Membership.status != MembershipStatus.VOID.value,
            )
        ).all()
    )
    active_count = sum(1 for m in memberships if m.status == MembershipStatus.ACTIVE.value)
    frozen_count = sum(1 for m in memberships if m.status == MembershipStatus.FROZEN.value)
    expired_in_range = int(
        db.scalar(
            select(func.count())
            .select_from(Membership)
            .where(
                Membership.merchant_id.in_(mids),
                Membership.status != MembershipStatus.VOID.value,
                Membership.ends_at.is_not(None),
                Membership.ends_at >= start,
                Membership.ends_at < end,
            )
        )
        or 0
    )

    return MembershipSummary(
        new_count=new_count,
        renew_count=renew_count,
        active_count=active_count,
        frozen_count=frozen_count,
        expired_in_range=expired_in_range,
    )


@dataclass
class CourseSummary:
    session_count: int
    booking_count: int
    full_session_count: int
    attended_count: int
    pt_consume_count: int
    pt_appointment_count: int = 0
    pt_completed_count: int = 0


def summarize_course(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> CourseSummary:
    start, end = _day_bounds(date_from, date_to)
    mids = _merchant_ids_for_site(db, site_id, merchant_id)
    if not mids:
        return CourseSummary(0, 0, 0, 0, 0)

    sessions = list(
        db.scalars(
            select(GroupSession).where(
                GroupSession.merchant_id.in_(mids),
                GroupSession.status != GroupSessionStatus.CANCELLED.value,
                GroupSession.starts_at >= start,
                GroupSession.starts_at < end,
            )
        ).all()
    )
    session_ids = [s.id for s in sessions]

    booking_count = 0
    attended_count = 0
    full_session_count = 0
    occupancy_statuses = {
        GroupBookingStatus.BOOKED.value,
        GroupBookingStatus.ATTENDED.value,
        GroupBookingStatus.NO_SHOW.value,
    }
    if session_ids:
        bookings = list(
            db.scalars(select(GroupBooking).where(GroupBooking.session_id.in_(session_ids))).all()
        )
        booking_count = sum(1 for b in bookings if b.status in occupancy_statuses)
        attended_count = sum(1 for b in bookings if b.status == GroupBookingStatus.ATTENDED.value)
        by_session: dict[int, int] = {}
        for b in bookings:
            if b.status in occupancy_statuses:
                by_session[b.session_id] = by_session.get(b.session_id, 0) + 1
        for s in sessions:
            if by_session.get(s.id, 0) >= s.capacity:
                full_session_count += 1

    pt_q = select(func.count()).select_from(AuditLog).where(
        AuditLog.action == "pt.consume",
        AuditLog.created_at >= start,
        AuditLog.created_at < end,
        AuditLog.site_id == site_id,
    )
    if merchant_id is not None:
        pt_q = pt_q.where(AuditLog.merchant_id == merchant_id)
    elif mids:
        pt_q = pt_q.where(AuditLog.merchant_id.in_(mids))
    pt_consume_count = int(db.scalar(pt_q) or 0)

    appointments = list(
        db.scalars(
            select(PtAppointment).where(
                PtAppointment.merchant_id.in_(mids),
                PtAppointment.starts_at >= start,
                PtAppointment.starts_at < end,
                PtAppointment.status != PtAppointmentStatus.CANCELLED.value,
            )
        ).all()
    )
    pt_completed = sum(
        1 for a in appointments if a.status == PtAppointmentStatus.COMPLETED.value
    )

    return CourseSummary(
        session_count=len(sessions),
        booking_count=booking_count,
        full_session_count=full_session_count,
        attended_count=attended_count,
        pt_consume_count=pt_consume_count,
        pt_appointment_count=len(appointments),
        pt_completed_count=pt_completed,
    )


# 收入口径：会员收入含办卡续卡，私教收入含课包核销销售，饮品收入取观野BAR 餐饮单
REVENUE_CATEGORIES: list[tuple[str, str, set[str]]] = [
    ("membership", "会员收入", {"membership"}),
    ("pt", "私教收入", {"pt_package", "pt"}),
    ("group", "团课收入", {"group"}),
    ("activity", "活动收入", {"activity"}),
    ("retail", "零售收入", {"retail"}),
    ("dining", "饮品收入", {"dining"}),
]


@dataclass
class RevenueSplitRow:
    category: str
    label: str
    charge_total: Decimal
    refund_total: Decimal
    net_total: Decimal


def summarize_revenue_split(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> list[RevenueSplitRow]:
    """按业务线拆分收入：会员 / 私教 / 团课 / 活动 / 零售 / 饮品。"""
    start, end = _day_bounds(date_from, date_to)
    stmt = (
        select(Order.order_type, Payment.kind, func.coalesce(func.sum(Payment.amount), 0))
        .join(Order, Order.id == Payment.order_id)
        .where(
            Order.site_id == site_id,
            Payment.created_at >= start,
            Payment.created_at < end,
        )
        .group_by(Order.order_type, Payment.kind)
    )
    if merchant_id is not None:
        stmt = stmt.where(Order.merchant_id == merchant_id)

    charge_by_type: dict[str, Decimal] = {}
    refund_by_type: dict[str, Decimal] = {}
    for order_type, kind, amount in db.execute(stmt).all():
        bucket = charge_by_type if kind == PaymentKind.CHARGE.value else refund_by_type
        bucket[order_type] = bucket.get(order_type, Decimal("0")) + Decimal(amount or 0)

    rows: list[RevenueSplitRow] = []
    covered: set[str] = set()
    for category, label, order_types in REVENUE_CATEGORIES:
        covered |= order_types
        charge = sum((charge_by_type.get(t, Decimal("0")) for t in order_types), Decimal("0"))
        refund = sum((refund_by_type.get(t, Decimal("0")) for t in order_types), Decimal("0"))
        rows.append(
            RevenueSplitRow(
                category=category,
                label=label,
                charge_total=_money(charge),
                refund_total=_money(refund),
                net_total=_money(charge - refund),
            )
        )
    other_charge = sum((v for k, v in charge_by_type.items() if k not in covered), Decimal("0"))
    other_refund = sum((v for k, v in refund_by_type.items() if k not in covered), Decimal("0"))
    if other_charge or other_refund:
        rows.append(
            RevenueSplitRow(
                category="other",
                label="其他收入",
                charge_total=_money(other_charge),
                refund_total=_money(other_refund),
                net_total=_money(other_charge - other_refund),
            )
        )
    return rows


@dataclass
class ActivitySummary:
    activity_count: int
    registered_count: int
    attended_count: int
    cancelled_count: int


def summarize_activity(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> ActivitySummary:
    """区间内开场的活动与报名出席情况。"""
    start, end = _day_bounds(date_from, date_to)
    mids = _merchant_ids_for_site(db, site_id, merchant_id)
    if not mids:
        return ActivitySummary(0, 0, 0, 0)

    activity_ids = list(
        db.scalars(
            select(Activity.id).where(
                Activity.merchant_id.in_(mids),
                Activity.starts_at >= start,
                Activity.starts_at < end,
            )
        ).all()
    )
    if not activity_ids:
        return ActivitySummary(0, 0, 0, 0)

    registrations = list(
        db.scalars(
            select(ActivityRegistration).where(
                ActivityRegistration.activity_id.in_(activity_ids)
            )
        ).all()
    )
    registered = sum(1 for r in registrations if r.status in OCCUPYING_REGISTRATION_STATUS)
    attended = sum(1 for r in registrations if r.status == RegistrationStatus.ATTENDED.value)
    cancelled = sum(1 for r in registrations if r.status == RegistrationStatus.CANCELLED.value)
    return ActivitySummary(
        activity_count=len(activity_ids),
        registered_count=registered,
        attended_count=attended,
        cancelled_count=cancelled,
    )


@dataclass
class InventorySkuRow:
    sku_id: int
    name: str
    stock_qty: int
    low_stock_threshold: int
    is_low: bool


@dataclass
class InventorySummary:
    sale_qty: int
    skus: list[InventorySkuRow]


def summarize_inventory(
    db: Session,
    *,
    site_id: int,
    date_from: date,
    date_to: date,
    merchant_id: int | None,
) -> InventorySummary:
    start, end = _day_bounds(date_from, date_to)
    mids = _merchant_ids_for_site(db, site_id, merchant_id)
    if not mids:
        return InventorySummary(0, [])

    sales = list(
        db.scalars(
            select(StockMovement).where(
                StockMovement.merchant_id.in_(mids),
                StockMovement.movement_type == StockMovementType.SALE.value,
                StockMovement.created_at >= start,
                StockMovement.created_at < end,
            )
        ).all()
    )
    sale_qty = sum(-m.quantity_delta for m in sales if m.quantity_delta < 0)

    skus = [
        InventorySkuRow(
            sku_id=s.id,
            name=s.name,
            stock_qty=s.stock_qty,
            low_stock_threshold=s.low_stock_threshold,
            is_low=s.stock_qty <= s.low_stock_threshold,
        )
        for s in db.scalars(
            select(RetailSku)
            .where(RetailSku.merchant_id.in_(mids), RetailSku.is_active.is_(True))
            .order_by(RetailSku.id.asc())
        ).all()
    ]
    return InventorySummary(sale_qty=sale_qty, skus=skus)
