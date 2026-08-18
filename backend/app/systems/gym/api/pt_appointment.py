"""私教一对一预约 API。"""

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.member_brief import load_member_briefs
from app.core.domain.subsystems import assert_merchant_has_system
from app.core.errors import AppError
from app.core.schemas.common import MemberBrief
from app.core.schemas.paging import PageOut, paginate
from app.systems.gym.models.appointment import PtAppointment, PtAppointmentStatus
from app.systems.gym.models.course import Coach, PtPackage, PtPackageStatus
from app.systems.gym.services.pt_appointment import (
    cancel_appointment,
    complete_appointment,
    create_appointment,
    mark_no_show,
    reschedule_appointment,
)
from app.systems.platform.models.member import Member, MerchantMember
from app.systems.platform.models.org import Merchant

router = APIRouter(tags=["pt-appointment"])


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class AppointmentIn(BaseModel):
    merchant_id: int | None = None
    member_id: int
    coach_id: int
    package_id: int | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=255)


class AppointmentPatch(BaseModel):
    coach_id: int | None = None
    starts_at: datetime
    ends_at: datetime
    location: str | None = Field(default=None, max_length=128)
    note: str | None = Field(default=None, max_length=255)


class CancelIn(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class NoShowIn(BaseModel):
    consume_session: bool = True


class AvailablePackageOut(BaseModel):
    id: int
    remaining_sessions: int
    ends_at: datetime | None = None


class AppointmentOut(ORMModel):
    id: int
    merchant_id: int
    member_id: int
    coach_id: int
    package_id: int | None
    starts_at: datetime
    ends_at: datetime
    status: str
    location: str | None
    note: str | None
    completed_at: datetime | None
    cancel_reason: str | None
    created_at: datetime
    member: MemberBrief | None = None
    coach_name: str | None = None
    package_remaining_sessions: int | None = None


def _appointment_out(
    db: Session,
    row: PtAppointment,
    *,
    briefs: dict[int, MemberBrief] | None = None,
    coach_names: dict[int, str] | None = None,
) -> AppointmentOut:
    member = (briefs or {}).get(row.member_id)
    if member is None:
        member = load_member_briefs(db, {row.member_id}).get(row.member_id)
    coach_name = (coach_names or {}).get(row.coach_id)
    if coach_name is None:
        coach = db.get(Coach, row.coach_id)
        coach_name = coach.display_name if coach else None
    remaining = None
    if row.package_id is not None:
        package = db.get(PtPackage, row.package_id)
        remaining = package.remaining_sessions if package else None
    return AppointmentOut(
        id=row.id,
        merchant_id=row.merchant_id,
        member_id=row.member_id,
        coach_id=row.coach_id,
        package_id=row.package_id,
        starts_at=row.starts_at,
        ends_at=row.ends_at,
        status=row.status,
        location=row.location,
        note=row.note,
        completed_at=row.completed_at,
        cancel_reason=row.cancel_reason,
        created_at=row.created_at,
        member=member,
        coach_name=coach_name,
        package_remaining_sessions=remaining,
    )


def _own_coach(db: Session, ctx: RequestContext, merchant_id: int) -> Coach | None:
    return db.scalar(
        select(Coach).where(Coach.merchant_id == merchant_id, Coach.staff_user_id == ctx.staff.id)
    )


def _load_appointment(db: Session, ctx: RequestContext, appointment_id: int) -> PtAppointment:
    appointment = db.get(PtAppointment, appointment_id)
    if appointment is None:
        raise AppError("not_found", "预约不存在", status_code=404)
    ctx.resolve_merchant_id(appointment.merchant_id)
    return appointment


@router.get("/pt-appointments", response_model=PageOut[AppointmentOut])
def list_appointments(
    merchant_id: int | None = None,
    coach_id: int | None = None,
    member_id: int | None = None,
    status: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    q: str | None = None,
    mine: bool = False,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:book", "pt:sell", "course:manage", "course:checkin")
    mid = ctx.resolve_merchant_id(merchant_id, required=False)
    stmt = select(PtAppointment)
    if mid is not None:
        stmt = stmt.where(PtAppointment.merchant_id == mid)
    else:
        stmt = stmt.where(
            PtAppointment.merchant_id.in_(select(Merchant.id).where(Merchant.site_id == ctx.site_id))
        )
    if mine and mid is not None:
        own = _own_coach(db, ctx, mid)
        if own is None:
            raise AppError("forbidden", "当前账号未绑定教练档案", status_code=403)
        stmt = stmt.where(PtAppointment.coach_id == own.id)
    elif coach_id is not None:
        stmt = stmt.where(PtAppointment.coach_id == coach_id)
    if member_id is not None:
        stmt = stmt.where(PtAppointment.member_id == member_id)
    if status:
        stmt = stmt.where(PtAppointment.status == status)
    if date_from is not None:
        stmt = stmt.where(PtAppointment.starts_at >= date_from)
    if date_to is not None:
        stmt = stmt.where(PtAppointment.starts_at <= date_to)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        member_ids = select(Member.id).where(or_(Member.phone.ilike(like), Member.name.ilike(like)))
        coach_ids = select(Coach.id).where(Coach.display_name.ilike(like))
        stmt = stmt.where(
            or_(PtAppointment.member_id.in_(member_ids), PtAppointment.coach_id.in_(coach_ids))
        )

    rows, total = paginate(
        db, stmt.order_by(PtAppointment.starts_at.desc()), page=page, page_size=page_size
    )
    briefs = load_member_briefs(db, {r.member_id for r in rows})
    coach_names = {
        c.id: c.display_name
        for c in db.scalars(
            select(Coach).where(Coach.id.in_({r.coach_id for r in rows} or {-1}))
        ).all()
    }
    items = [_appointment_out(db, r, briefs=briefs, coach_names=coach_names) for r in rows]
    return PageOut(items=items, total=total, page=page, page_size=page_size)


@router.get("/pt-appointments/available-packages", response_model=list[AvailablePackageOut])
def list_member_available_packages(
    member_id: int,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """排期时选课包：返回该会员在本商户可用的课包。"""
    ctx.require_permission("pt:book", "pt:sell", "course:manage")
    mid = ctx.resolve_merchant_id(merchant_id)
    rows = list(
        db.scalars(
            select(PtPackage)
            .where(
                PtPackage.merchant_id == mid,
                PtPackage.member_id == member_id,
                PtPackage.status == PtPackageStatus.ACTIVE.value,
                PtPackage.remaining_sessions > 0,
            )
            .order_by(PtPackage.id.desc())
        ).all()
    )
    return [
        AvailablePackageOut(
            id=r.id, remaining_sessions=r.remaining_sessions, ends_at=r.ends_at
        )
        for r in rows
    ]


@router.get("/pt-appointments/{appointment_id}", response_model=AppointmentOut)
def get_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:book", "pt:sell", "course:manage", "course:checkin")
    appointment = _load_appointment(db, ctx, appointment_id)
    return _appointment_out(db, appointment)


@router.post("/pt-appointments", response_model=AppointmentOut)
def create_pt_appointment(
    body: AppointmentIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:book", "pt:sell", "course:manage")
    mid = ctx.resolve_merchant_id(body.merchant_id)
    assert_merchant_has_system(db, mid, "gym")
    member = db.get(Member, body.member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    link = db.scalar(
        select(MerchantMember).where(
            MerchantMember.member_id == member.id, MerchantMember.merchant_id == mid
        )
    )
    if link is None:
        db.add(MerchantMember(member_id=member.id, merchant_id=mid))
        db.flush()

    appointment = create_appointment(
        db,
        merchant_id=mid,
        site_id=ctx.site_id,
        member_id=body.member_id,
        coach_id=body.coach_id,
        package_id=body.package_id,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        location=body.location,
        note=body.note,
        actor_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(appointment)
    return _appointment_out(db, appointment)


@router.patch("/pt-appointments/{appointment_id}", response_model=AppointmentOut)
def patch_pt_appointment(
    appointment_id: int,
    body: AppointmentPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:book", "course:manage")
    appointment = _load_appointment(db, ctx, appointment_id)
    reschedule_appointment(
        db,
        appointment,
        starts_at=body.starts_at,
        ends_at=body.ends_at,
        site_id=ctx.site_id,
        coach_id=body.coach_id,
        location=body.location,
        note=body.note,
        fields_set=set(body.model_fields_set),
        actor_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(appointment)
    return _appointment_out(db, appointment)


@router.post("/pt-appointments/{appointment_id}/cancel", response_model=AppointmentOut)
def cancel_pt_appointment(
    appointment_id: int,
    body: CancelIn | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("pt:book", "course:manage")
    appointment = _load_appointment(db, ctx, appointment_id)
    cancel_appointment(
        db,
        appointment,
        site_id=ctx.site_id,
        reason=(body.reason if body else None),
        actor_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(appointment)
    return _appointment_out(db, appointment)


@router.post("/pt-appointments/{appointment_id}/complete", response_model=AppointmentOut)
def complete_pt_appointment(
    appointment_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """完成私教课：核销课时并按规则计提教练提成。"""
    ctx.require_permission("course:checkin", "pt:book", "course:manage")
    appointment = _load_appointment(db, ctx, appointment_id)
    complete_appointment(db, appointment, site_id=ctx.site_id, actor_staff_id=ctx.staff.id)
    db.commit()
    db.refresh(appointment)
    return _appointment_out(db, appointment)


@router.post("/pt-appointments/{appointment_id}/no-show", response_model=AppointmentOut)
def no_show_pt_appointment(
    appointment_id: int,
    body: NoShowIn | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("course:checkin", "pt:book", "course:manage")
    appointment = _load_appointment(db, ctx, appointment_id)
    mark_no_show(
        db,
        appointment,
        site_id=ctx.site_id,
        consume_session=body.consume_session if body else True,
        actor_staff_id=ctx.staff.id,
    )
    db.commit()
    db.refresh(appointment)
    return _appointment_out(db, appointment)
