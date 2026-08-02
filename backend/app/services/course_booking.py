"""团课预约、取消与会籍资格校验。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models.course import (
    GroupBooking,
    GroupBookingStatus,
    GroupCourse,
    GroupSession,
    GroupSessionStatus,
)
from app.models.membership import Membership, MembershipStatus
from app.services.audit import write_audit
from app.services.notifications import write_notification


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def has_active_membership(db: Session, merchant_id: int, member_id: int) -> bool:
    """本商户是否存在生效会籍（active 且未过 ends_at）。"""
    now = _now()
    rows = db.scalars(
        select(Membership).where(
            Membership.merchant_id == merchant_id,
            Membership.member_id == member_id,
            Membership.status == MembershipStatus.ACTIVE.value,
        )
    ).all()
    for m in rows:
        ends = _ensure_aware(m.ends_at)
        if ends is not None and ends < now:
            continue
        return True
    return False


def booked_count(db: Session, session_id: int) -> int:
    return int(
        db.scalar(
            select(func.count())
            .select_from(GroupBooking)
            .where(
                GroupBooking.session_id == session_id,
                GroupBooking.status == GroupBookingStatus.BOOKED.value,
            )
        )
        or 0
    )


def book_group_session(
    db: Session,
    session: GroupSession,
    member_id: int,
    *,
    actor_staff_id: int | None = None,
    site_id: int | None = None,
) -> GroupBooking:
    # 行锁（PostgreSQL 生效；SQLite 测试依赖应用层计数）
    locked = db.scalar(
        select(GroupSession).where(GroupSession.id == session.id).with_for_update()
    )
    if locked is None:
        raise AppError("not_found", "场次不存在", status_code=404)
    session = locked

    if session.status != GroupSessionStatus.OPEN.value:
        raise AppError("session_closed", "场次不可预约", status_code=400)

    course = db.get(GroupCourse, session.course_id)
    if course is None:
        raise AppError("not_found", "课程不存在", status_code=404)

    starts = _ensure_aware(session.starts_at)
    assert starts is not None
    if starts <= _now():
        raise AppError("session_started", "场次已开始，不可预约", status_code=400)
    if course.book_ahead_minutes > 0 and starts - _now() < timedelta(minutes=course.book_ahead_minutes):
        raise AppError("too_late_to_book", "已超过可预约时限", status_code=400)

    if not has_active_membership(db, session.merchant_id, member_id):
        raise AppError("membership_required", "需要本商户生效会籍方可预约", status_code=400)

    existing = db.scalar(
        select(GroupBooking).where(
            GroupBooking.session_id == session.id,
            GroupBooking.member_id == member_id,
        )
    )
    if existing is not None and existing.status == GroupBookingStatus.BOOKED.value:
        raise AppError("already_booked", "已预约该场次", status_code=400)

    if booked_count(db, session.id) >= session.capacity:
        raise AppError("session_full", "场次已满员", status_code=400)

    if existing is not None:
        # 取消后再约：复用同一行
        existing.status = GroupBookingStatus.BOOKED.value
        booking = existing
    else:
        booking = GroupBooking(
            session_id=session.id,
            merchant_id=session.merchant_id,
            member_id=member_id,
            status=GroupBookingStatus.BOOKED.value,
        )
        db.add(booking)
        db.flush()

    write_audit(
        db,
        action="group.book",
        target_type="group_booking",
        target_id=booking.id,
        summary=f"代约 session={session.id} member={member_id}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=session.merchant_id,
    )
    write_notification(
        db,
        site_id=site_id,
        merchant_id=session.merchant_id,
        member_id=member_id,
        event_type="group.booked",
        title="团课预约成功",
        body=f"已预约场次 #{session.id}",
    )
    return booking


def cancel_group_booking(
    db: Session,
    booking: GroupBooking,
    session: GroupSession,
    course: GroupCourse,
    *,
    force: bool = False,
    actor_staff_id: int | None = None,
    site_id: int | None = None,
) -> GroupBooking:
    if booking.status != GroupBookingStatus.BOOKED.value:
        raise AppError("invalid_state", "仅已约记录可取消", status_code=400)

    starts = _ensure_aware(session.starts_at)
    assert starts is not None
    if not force and course.cancel_ahead_minutes > 0:
        if starts - _now() < timedelta(minutes=course.cancel_ahead_minutes):
            raise AppError("too_late_to_cancel", "已超过可取消时限", status_code=400)

    booking.status = GroupBookingStatus.CANCELLED.value
    write_audit(
        db,
        action="group.cancel",
        target_type="group_booking",
        target_id=booking.id,
        summary=f"取消预约 force={force}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=booking.merchant_id,
    )
    return booking


def checkin_group_booking(
    db: Session,
    booking: GroupBooking,
    status: str,
    *,
    actor_staff_id: int | None = None,
    site_id: int | None = None,
) -> GroupBooking:
    if status not in {GroupBookingStatus.ATTENDED.value, GroupBookingStatus.NO_SHOW.value}:
        raise AppError("invalid_status", "签到状态无效", status_code=400)
    if booking.status not in {
        GroupBookingStatus.BOOKED.value,
        GroupBookingStatus.ATTENDED.value,
        GroupBookingStatus.NO_SHOW.value,
    }:
        raise AppError("invalid_state", "当前预约不可签到", status_code=400)

    booking.status = status
    write_audit(
        db,
        action="group.checkin",
        target_type="group_booking",
        target_id=booking.id,
        summary=f"签到 {status}",
        actor_staff_id=actor_staff_id,
        site_id=site_id,
        merchant_id=booking.merchant_id,
    )
    return booking
