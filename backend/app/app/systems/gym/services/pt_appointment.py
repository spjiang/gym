"""私教一对一预约：排期、改期、取消与完成核销。"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import AppError
from app.systems.gym.models.appointment import (
    BLOCKING_APPOINTMENT_STATUS,
    PtAppointment,
    PtAppointmentStatus,
)
from app.systems.gym.models.course import (
    Coach,
    PtOrderLink,
    PtPackage,
    PtPackageProduct,
    PtPackageStatus,
)
from app.systems.gym.services.commission import accrue_pt_session_commission
from app.systems.gym.services.pt_fulfillment import consume_pt_package
from app.systems.platform.models.commerce import Order, OrderStatus
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.notifications import write_notification


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def assert_no_conflict(
    db: Session,
    *,
    merchant_id: int,
    coach_id: int,
    member_id: int,
    starts_at: datetime,
    ends_at: datetime,
    exclude_id: int | None = None,
) -> None:
    """同教练、同会员的时段不允许重叠。"""
    stmt = select(PtAppointment).where(
        PtAppointment.merchant_id == merchant_id,
        PtAppointment.status.in_(list(BLOCKING_APPOINTMENT_STATUS)),
        PtAppointment.starts_at < ends_at,
        PtAppointment.ends_at > starts_at,
    )
    if exclude_id is not None:
        stmt = stmt.where(PtAppointment.id != exclude_id)
    for row in db.scalars(stmt).all():
        if row.coach_id == coach_id:
            raise AppError("coach_busy", "该教练在此时段已有排期", status_code=409)
        if row.member_id == member_id:
            raise AppError("member_busy", "该会员在此时段已有私教课", status_code=409)


def _validate_window(starts_at: datetime, ends_at: datetime) -> tuple[datetime, datetime]:
    start = _ensure_aware(starts_at)
    end = _ensure_aware(ends_at)
    if start is None or end is None:
        raise AppError("invalid_time", "请填写上课时间", status_code=400)
    if end <= start:
        raise AppError("invalid_time", "结束时间必须晚于开始时间", status_code=400)
    if (end - start).total_seconds() > 8 * 3600:
        raise AppError("invalid_time", "单节私教课时长不可超过 8 小时", status_code=400)
    return start, end


def _assert_package_usable(package: PtPackage, *, merchant_id: int, member_id: int) -> None:
    if package.merchant_id != merchant_id:
        raise AppError("forbidden", "课包不属于当前商户", status_code=403)
    if package.member_id != member_id:
        raise AppError("invalid_package", "课包不属于该会员", status_code=400)
    if package.status != PtPackageStatus.ACTIVE.value:
        raise AppError("package_unavailable", "课包不可用", status_code=400)
    if package.remaining_sessions <= 0:
        raise AppError("no_sessions", "课包剩余课时不足", status_code=400)


def create_appointment(
    db: Session,
    *,
    merchant_id: int,
    site_id: int,
    member_id: int,
    coach_id: int,
    package_id: int | None,
    starts_at: datetime,
    ends_at: datetime,
    location: str | None,
    note: str | None,
    actor_staff_id: int | None,
) -> PtAppointment:
    start, end = _validate_window(starts_at, ends_at)
    coach = db.get(Coach, coach_id)
    if coach is None or coach.merchant_id != merchant_id:
        raise AppError("not_found", "教练不存在", status_code=404)
    if not coach.is_active:
        raise AppError("coach_inactive", "教练已停用，不可排课", status_code=400)

    if package_id is not None:
        package = db.get(PtPackage, package_id)
        if package is None:
            raise AppError("not_found", "课包不存在", status_code=404)
        _assert_package_usable(package, merchant_id=merchant_id, member_id=member_id)
        booked_count = int(
            db.scalar(
                select(func.count())
                .select_from(PtAppointment)
                .where(
                    PtAppointment.package_id == package_id,
                    PtAppointment.status == PtAppointmentStatus.BOOKED.value,
                )
            )
            or 0
        )
        if booked_count >= package.remaining_sessions:
            raise AppError("no_sessions", "该课包待上课程已占满剩余课时", status_code=400)

    assert_no_conflict(
        db,
        merchant_id=merchant_id,
        coach_id=coach_id,
        member_id=member_id,
        starts_at=start,
        ends_at=end,
    )

    appointment = PtAppointment(
        merchant_id=merchant_id,
        member_id=member_id,
        coach_id=coach_id,
        package_id=package_id,
        starts_at=start,
        ends_at=end,
        status=PtAppointmentStatus.BOOKED.value,
        location=(location or "").strip() or None,
        note=(note or "").strip() or None,
    )
    db.add(appointment)
    db.flush()
    write_audit(
        db,
        action="pt_appointment.create",
        target_type="pt_appointment",
        target_id=appointment.id,
        summary=f"私教排期 coach={coach_id} member={member_id}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=merchant_id,
    )
    write_notification(
        db,
        site_id=site_id,
        merchant_id=merchant_id,
        member_id=member_id,
        event_type="pt_appointment.booked",
        title="私教课已预约",
        body=f"{coach.display_name} 教练 {start:%Y-%m-%d %H:%M} 私教课已排期",
    )
    return appointment


def reschedule_appointment(
    db: Session,
    appointment: PtAppointment,
    *,
    starts_at: datetime,
    ends_at: datetime,
    site_id: int,
    coach_id: int | None = None,
    location: str | None = None,
    note: str | None = None,
    fields_set: set[str] | None = None,
    actor_staff_id: int | None = None,
) -> PtAppointment:
    if appointment.status != PtAppointmentStatus.BOOKED.value:
        raise AppError("invalid_state", "仅待上课的排期可改期", status_code=400)
    start, end = _validate_window(starts_at, ends_at)
    changed = fields_set or set()

    target_coach_id = appointment.coach_id
    if coach_id is not None and coach_id != appointment.coach_id:
        coach = db.get(Coach, coach_id)
        if coach is None or coach.merchant_id != appointment.merchant_id:
            raise AppError("not_found", "教练不存在", status_code=404)
        if not coach.is_active:
            raise AppError("coach_inactive", "教练已停用，不可排课", status_code=400)
        target_coach_id = coach_id

    assert_no_conflict(
        db,
        merchant_id=appointment.merchant_id,
        coach_id=target_coach_id,
        member_id=appointment.member_id,
        starts_at=start,
        ends_at=end,
        exclude_id=appointment.id,
    )
    appointment.coach_id = target_coach_id
    appointment.starts_at = start
    appointment.ends_at = end
    if "location" in changed:
        appointment.location = (location or "").strip() or None
    if "note" in changed:
        appointment.note = (note or "").strip() or None
    write_audit(
        db,
        action="pt_appointment.reschedule",
        target_type="pt_appointment",
        target_id=appointment.id,
        summary=f"改期至 {start:%Y-%m-%d %H:%M}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
    )
    write_notification(
        db,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
        member_id=appointment.member_id,
        event_type="pt_appointment.rescheduled",
        title="私教课已改期",
        body=f"新的上课时间：{start:%Y-%m-%d %H:%M}",
    )
    db.flush()
    return appointment


def cancel_appointment(
    db: Session,
    appointment: PtAppointment,
    *,
    site_id: int,
    reason: str | None,
    actor_staff_id: int | None = None,
) -> PtAppointment:
    if appointment.status != PtAppointmentStatus.BOOKED.value:
        raise AppError("invalid_state", "仅待上课的排期可取消", status_code=400)
    appointment.status = PtAppointmentStatus.CANCELLED.value
    appointment.cancel_reason = (reason or "").strip() or None
    write_audit(
        db,
        action="pt_appointment.cancel",
        target_type="pt_appointment",
        target_id=appointment.id,
        summary=f"取消排期：{appointment.cancel_reason or '未填写原因'}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
    )
    write_notification(
        db,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
        member_id=appointment.member_id,
        event_type="pt_appointment.cancelled",
        title="私教课已取消",
        body=f"{appointment.starts_at:%Y-%m-%d %H:%M} 的私教课已取消",
    )
    db.flush()
    return appointment


def pt_session_unit_price(db: Session, package: PtPackage) -> Decimal:
    """单节课时单价：优先按课包实付成交额摊分，无成交订单时按卡种标价摊分。"""
    product = db.get(PtPackageProduct, package.product_id)
    sessions = int(product.session_count) if product is not None else 0
    if sessions <= 0:
        return Decimal("0")
    link = db.scalar(select(PtOrderLink).where(PtOrderLink.fulfilled_package_id == package.id))
    if link is not None:
        order = db.get(Order, link.order_id)
        if order is not None and order.status == OrderStatus.PAID.value:
            return Decimal(order.amount) / Decimal(sessions)
    return Decimal(product.price) / Decimal(sessions)


def complete_appointment(
    db: Session,
    appointment: PtAppointment,
    *,
    site_id: int,
    actor_staff_id: int | None = None,
) -> PtAppointment:
    """完成私教课：核销课包课时并按规则计提教练提成。"""
    if appointment.status != PtAppointmentStatus.BOOKED.value:
        raise AppError("invalid_state", "仅待上课的排期可完成", status_code=400)

    base_amount = Decimal("0")
    if appointment.package_id is not None:
        package = db.get(PtPackage, appointment.package_id)
        if package is None:
            raise AppError("not_found", "课包不存在", status_code=404)
        consume_pt_package(db, package, actor_staff_id=actor_staff_id)
        base_amount = pt_session_unit_price(db, package)
    else:
        coach = db.get(Coach, appointment.coach_id)
        if coach is not None and coach.hourly_rate is not None:
            base_amount = Decimal(coach.hourly_rate)

    appointment.status = PtAppointmentStatus.COMPLETED.value
    appointment.completed_at = _now()
    accrue_pt_session_commission(
        db,
        merchant_id=appointment.merchant_id,
        appointment_id=appointment.id,
        coach_id=appointment.coach_id,
        member_id=appointment.member_id,
        base_amount=base_amount,
        at=_ensure_aware(appointment.starts_at) or _now(),
    )
    write_audit(
        db,
        action="pt_appointment.complete",
        target_type="pt_appointment",
        target_id=appointment.id,
        summary="私教课完成并核销课时",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
    )
    db.flush()
    return appointment


def mark_no_show(
    db: Session,
    appointment: PtAppointment,
    *,
    site_id: int,
    consume_session: bool,
    actor_staff_id: int | None = None,
) -> PtAppointment:
    """标记会员未到；按商户规则决定是否照常扣课时。"""
    if appointment.status != PtAppointmentStatus.BOOKED.value:
        raise AppError("invalid_state", "仅待上课的排期可标记未到", status_code=400)
    if consume_session and appointment.package_id is not None:
        package = db.get(PtPackage, appointment.package_id)
        if package is None:
            raise AppError("not_found", "课包不存在", status_code=404)
        consume_pt_package(db, package, actor_staff_id=actor_staff_id)
    appointment.status = PtAppointmentStatus.NO_SHOW.value
    write_audit(
        db,
        action="pt_appointment.no_show",
        target_type="pt_appointment",
        target_id=appointment.id,
        summary=f"标记未到{'，已扣课时' if consume_session else '，未扣课时'}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=appointment.merchant_id,
    )
    db.flush()
    return appointment
