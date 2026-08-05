"""会员主档。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.common import MemberCreateIn, MemberLinkIn, MemberOut, MemberUpdateIn
from app.core.schemas.paging import PageOut
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant
from app.systems.platform.models.otp import MemberOtpChallenge
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/members", tags=["members"])


def _member_out(db: Session, m: Member) -> MemberOut:
    links = list(db.scalars(select(MerchantMember).where(MerchantMember.member_id == m.id)).all())
    first_name = None
    if m.first_merchant_id is not None:
        fm = db.get(Merchant, m.first_merchant_id)
        first_name = fm.name if fm else None
    return MemberOut(
        id=m.id,
        site_id=m.site_id,
        phone=m.phone,
        name=m.name,
        face_status=m.face_status,
        created_at=m.created_at,
        merchant_ids=[x.merchant_id for x in links],
        acquisition_source=m.acquisition_source,
        first_merchant_id=m.first_merchant_id,
        first_merchant_name=first_name,
    )


def _member_filters(ctx: RequestContext, q: str | None):
    """构造会员列表过滤条件。"""
    filters = [Member.site_id == ctx.site_id]
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        member_ids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
        filters.append(Member.id.in_(member_ids))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(Member.phone.ilike(like), Member.name.ilike(like)))
    return filters


@router.get("", response_model=PageOut[MemberOut])
def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("member:read", "member:write")
    filters = _member_filters(ctx, q)
    total = db.scalar(select(func.count()).select_from(Member).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(Member)
            .where(*filters)
            .order_by(Member.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(
        items=[_member_out(db, m) for m in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/{member_id}", response_model=MemberOut)
def get_member(
    member_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("member:read", "member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        linked = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == member_id, MerchantMember.merchant_id == mid
            )
        )
        if linked is None:
            raise AppError("forbidden", "无权查看该会员", status_code=403)
    return _member_out(db, member)


@router.post("", response_model=MemberOut)
def create_member(
    body: MemberCreateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("member:write")
    phone = body.phone.strip()
    name = body.name.strip()
    if not phone or not name:
        raise AppError("validation_error", "手机号与姓名为必填", status_code=422)

    link_mid: int | None = None
    if body.merchant_id is not None or not ctx.is_site_admin:
        link_mid = ctx.resolve_merchant_id(body.merchant_id)
        merchant = db.get(Merchant, link_mid)
        if merchant is None or merchant.site_id != ctx.site_id:
            raise AppError("not_found", "商户不存在", status_code=404)

    member = Member(
        site_id=ctx.site_id,
        phone=phone,
        name=name,
        face_status=FaceStatus.NOT_ENROLLED.value,
        acquisition_source=(
            AcquisitionSource.MERCHANT.value if link_mid is not None else AcquisitionSource.PLATFORM.value
        ),
        first_merchant_id=link_mid,
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该手机号已存在于本场地", status_code=409) from exc

    if link_mid is not None:
        db.add(MerchantMember(merchant_id=link_mid, member_id=member.id))

    write_audit(
        db,
        action="member.create",
        target_type="member",
        target_id=member.id,
        summary=f"创建会员 {member.phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=link_mid,
    )
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.patch("/{member_id}", response_model=MemberOut)
def update_member(
    member_id: int,
    body: MemberUpdateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """编辑会员姓名。"""
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        linked = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == member_id, MerchantMember.merchant_id == mid
            )
        )
        if linked is None:
            raise AppError("forbidden", "无权编辑该会员", status_code=403)
    member.name = body.name.strip()
    write_audit(
        db,
        action="member.update",
        target_type="member",
        target_id=member.id,
        summary=f"更新会员姓名 {member.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.post("/{member_id}/merchants", response_model=MemberOut)
def link_merchant(
    member_id: int,
    body: MemberLinkIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    mid = ctx.resolve_merchant_id(body.merchant_id)
    exists = db.scalar(
        select(MerchantMember).where(
            MerchantMember.member_id == member_id, MerchantMember.merchant_id == mid
        )
    )
    if not exists:
        db.add(MerchantMember(merchant_id=mid, member_id=member_id))
        write_audit(
            db,
            action="member.link_merchant",
            target_type="member",
            target_id=member_id,
            summary=f"关联商户 {mid}",
            actor_staff_id=ctx.staff.id,
            site_id=ctx.site_id,
            merchant_id=mid,
        )
        db.commit()
    return _member_out(db, member)


@router.delete("/{member_id}")
def delete_member(
    member_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """删除会员主档；若仍有会籍/通行/订单等业务关联则拒绝。"""
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)

    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        linked = db.scalar(
            select(MerchantMember).where(
                MerchantMember.member_id == member_id, MerchantMember.merchant_id == mid
            )
        )
        if linked is None:
            raise AppError("forbidden", "无权删除该会员", status_code=403)

    phone = member.phone
    db.execute(delete(MerchantMember).where(MerchantMember.member_id == member_id))
    db.execute(delete(MemberOtpChallenge).where(MemberOtpChallenge.member_id == member_id))
    db.delete(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError(
            "conflict",
            "该会员存在关联业务数据（会籍/通行/订单等），无法删除",
            status_code=409,
        ) from exc

    write_audit(
        db,
        action="member.delete",
        target_type="member",
        target_id=member_id,
        summary=f"删除会员 {phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    return {"ok": True}
