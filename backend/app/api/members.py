"""会员主档。"""

from fastapi import APIRouter, Depends
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.deps import RequestContext, get_current_context
from app.errors import AppError
from app.models.member import FaceStatus, Member, MerchantMember
from app.models.org import Merchant
from app.models.otp import MemberOtpChallenge
from app.schemas.common import MemberCreateIn, MemberLinkIn, MemberOut
from app.services.audit import write_audit

router = APIRouter(prefix="/members", tags=["members"])


def _member_out(db: Session, m: Member) -> MemberOut:
    links = list(db.scalars(select(MerchantMember).where(MerchantMember.member_id == m.id)).all())
    return MemberOut(
        id=m.id,
        site_id=m.site_id,
        phone=m.phone,
        name=m.name,
        face_status=m.face_status,
        created_at=m.created_at,
        merchant_ids=[x.merchant_id for x in links],
    )


@router.get("", response_model=list[MemberOut])
def list_members(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("member:read", "member:write")
    q = select(Member).where(Member.site_id == ctx.site_id)
    if not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id()
        member_ids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
        q = q.where(Member.id.in_(member_ids))
    rows = list(db.scalars(q.order_by(Member.id.desc())).all())
    return [_member_out(db, m) for m in rows]


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
    member = Member(
        site_id=ctx.site_id,
        phone=phone,
        name=name,
        face_status=FaceStatus.NOT_ENROLLED.value,
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该手机号已存在于本场地", status_code=409) from exc

    if body.merchant_id is not None or not ctx.is_site_admin:
        mid = ctx.resolve_merchant_id(body.merchant_id)
        merchant = db.get(Merchant, mid)
        if merchant is None or merchant.site_id != ctx.site_id:
            raise AppError("not_found", "商户不存在", status_code=404)
        db.add(MerchantMember(merchant_id=mid, member_id=member.id))

    write_audit(
        db,
        action="member.create",
        target_type="member",
        target_id=member.id,
        summary=f"创建会员 {member.phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=body.merchant_id,
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
