"""经营报表：支付流水汇总与会籍/课程/库存看板。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.systems.platform.models.audit import AuditLog
from app.systems.platform.models.commerce import Order, Payment, PaymentKind
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

    return CourseSummary(
        session_count=len(sessions),
        booking_count=booking_count,
        full_session_count=full_session_count,
        attended_count=attended_count,
        pt_consume_count=pt_consume_count,
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
