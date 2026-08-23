"""会员主档。"""

from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import delete, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.common import (
    MemberCreateIn,
    MemberImportErrorOut,
    MemberImportOut,
    MemberLinkIn,
    MemberOut,
    MemberReferrerMixin,
    MemberUpdateIn,
    PasswordResetIn,
)
from app.core.schemas.paging import PageOut
from app.core.security import hash_password
from app.systems.platform.models.identity import StaffUser
from app.systems.platform.models.member import AcquisitionSource, FaceStatus, Member, MerchantMember
from app.systems.platform.models.org import Merchant
from app.systems.platform.models.otp import MemberOtpChallenge
from app.systems.platform.models.promoter import PromoterCode
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.promotion import ensure_member_promoter_code
from app.systems.platform.services.member_import import (
    XLSX_MIME,
    build_member_import_template,
    import_members_for_merchant,
    parse_member_import,
)
from app.systems.platform.api.uploads import save_upload_file

router = APIRouter(prefix="/members", tags=["members"])


def _referrer_display(db: Session, m: Member) -> str | None:
    """推荐人展示名：会员推广或登记姓名。"""
    if m.referrer_member_id is not None:
        ref = db.get(Member, m.referrer_member_id)
        if ref is not None:
            return f"会员 {ref.name} {ref.phone}"
    return m.referrer_note


def _member_out(db: Session, m: Member) -> MemberOut:
    links = list(db.scalars(select(MerchantMember).where(MerchantMember.member_id == m.id)).all())
    first_name = None
    if m.first_merchant_id is not None:
        fm = db.get(Merchant, m.first_merchant_id)
        first_name = fm.name if fm else None
    referred_count = int(
        db.scalar(
            select(func.count()).select_from(Member).where(Member.referrer_member_id == m.id)
        )
        or 0
    )
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
        has_password=bool(m.password_hash),
        referrer_member_id=m.referrer_member_id,
        referrer_note=m.referrer_note,
        referral_code=m.referral_code,
        referrer_display=_referrer_display(db, m),
        referred_count=referred_count,
        avatar_url=m.avatar_url,
    )


def _assert_no_referrer_cycle(db: Session, member: Member, referrer_id: int) -> None:
    """推荐链不能自指或成环。"""
    if referrer_id == member.id:
        raise AppError("invalid_referrer", "推荐人不能是本人", status_code=400)
    seen = {member.id}
    cursor_id: int | None = referrer_id
    while cursor_id is not None:
        if cursor_id in seen:
            raise AppError("invalid_referrer", "推荐关系不能形成环", status_code=400)
        seen.add(cursor_id)
        cursor = db.get(Member, cursor_id)
        if cursor is None:
            break
        cursor_id = cursor.referrer_member_id


def _apply_referrer(
    db: Session,
    ctx: RequestContext,
    member: Member,
    body: MemberReferrerMixin,
    *,
    fields_set: set[str],
) -> None:
    """校验并写入推荐关系；推广码需存在且启用。"""
    if "referrer_member_id" in fields_set:
        if body.referrer_member_id is not None:
            ref = db.get(Member, body.referrer_member_id)
            if ref is None or ref.site_id != ctx.site_id:
                raise AppError("not_found", "推荐会员不存在", status_code=404)
            _assert_no_referrer_cycle(db, member, body.referrer_member_id)
        member.referrer_member_id = body.referrer_member_id
    if "referrer_note" in fields_set:
        member.referrer_note = (body.referrer_note or "").strip() or None
    if "referral_code" in fields_set:
        code = (body.referral_code or "").strip().upper()
        if code:
            promoter = db.scalar(select(PromoterCode).where(PromoterCode.code == code))
            if promoter is None or promoter.site_id != ctx.site_id:
                raise AppError("not_found", "推广码不存在", status_code=404)
            if not promoter.is_active:
                raise AppError("invalid_code", "推广码已停用", status_code=400)
            if promoter.subject_member_id:
                _assert_no_referrer_cycle(db, member, promoter.subject_member_id)
            member.referral_code = code
        else:
            member.referral_code = None


def _assert_member_in_scope(db: Session, ctx: RequestContext, member: Member) -> None:
    """非场地超管仅能操作已挂靠本商户的会员。"""
    if ctx.is_site_wide:
        return
    mid = ctx.resolve_merchant_id()
    linked = db.scalar(
        select(MerchantMember).where(
            MerchantMember.member_id == member.id, MerchantMember.merchant_id == mid
        )
    )
    if linked is None:
        raise AppError("forbidden", "无权操作该会员", status_code=403)


def _member_filters(
    ctx: RequestContext,
    q: str | None,
    *,
    merchant_id: int | None = None,
    face_status: str | None = None,
    has_password: bool | None = None,
    referrer_member_id: int | None = None,
    referral_code: str | None = None,
    has_referrer: bool | None = None,
):
    """构造会员列表过滤条件。"""
    filters = [Member.site_id == ctx.site_id]
    if not ctx.is_site_wide:
        mid = ctx.resolve_merchant_id()
        member_ids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == mid)
        filters.append(Member.id.in_(member_ids))
    elif merchant_id is not None:
        member_ids = select(MerchantMember.member_id).where(MerchantMember.merchant_id == merchant_id)
        filters.append(Member.id.in_(member_ids))
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(Member.phone.ilike(like), Member.name.ilike(like)))
    if face_status:
        filters.append(Member.face_status == face_status)
    if has_password is True:
        filters.append(Member.password_hash.is_not(None))
    elif has_password is False:
        filters.append(Member.password_hash.is_(None))
    if referrer_member_id is not None:
        filters.append(Member.referrer_member_id == referrer_member_id)
    if referral_code:
        filters.append(Member.referral_code == referral_code.strip().upper())
    referred = or_(
        Member.referrer_member_id.is_not(None),
        Member.referrer_note.is_not(None),
        Member.referral_code.is_not(None),
    )
    if has_referrer is True:
        filters.append(referred)
    elif has_referrer is False:
        filters.append(~referred)
    return filters


@router.get("", response_model=PageOut[MemberOut])
def list_members(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    merchant_id: int | None = None,
    face_status: str | None = None,
    has_password: bool | None = None,
    referrer_member_id: int | None = None,
    referral_code: str | None = None,
    has_referrer: bool | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("member:read", "member:write")
    filters = _member_filters(
        ctx,
        q,
        merchant_id=merchant_id,
        face_status=face_status,
        has_password=has_password,
        referrer_member_id=referrer_member_id,
        referral_code=referral_code,
        has_referrer=has_referrer,
    )
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


@router.get("/import-template")
def download_member_import_template(ctx: RequestContext = Depends(get_current_context)):
    """下载商户会员导入 Excel 模板。"""
    ctx.require_permission("member:read", "member:write")
    filename = "商户会员导入模板.xlsx"
    return StreamingResponse(
        iter([build_member_import_template()]),
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": (
                f"attachment; filename=\"merchant-members.xlsx\"; filename*=UTF-8''{quote(filename)}"
            )
        },
    )


@router.post("/import", response_model=MemberImportOut)
async def import_members(
    merchant_id: int | None = None,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """按 Excel 模板导入会员，并挂靠到当前商户。"""
    ctx.require_permission("member:write")
    mid = ctx.resolve_merchant_id(merchant_id)
    merchant = db.get(Merchant, mid)
    if merchant is None or merchant.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)

    filename = (file.filename or "").lower()
    if filename and not filename.endswith(".xlsx"):
        raise AppError("invalid_file", "仅支持 .xlsx 模板文件", status_code=400)
    data = await file.read()
    rows, issues = parse_member_import(data)
    counts = import_members_for_merchant(db, site_id=ctx.site_id, merchant_id=mid, rows=rows)
    write_audit(
        db,
        action="member.import",
        target_type="merchant",
        target_id=mid,
        summary=(
            f"导入会员到 {merchant.name}：新增 {counts['created']}，"
            f"挂靠 {counts['linked']}，跳过 {counts['skipped']}，失败 {len(issues)}"
        ),
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=mid,
    )
    db.commit()
    return MemberImportOut(
        merchant_id=mid,
        merchant_name=merchant.name,
        total_rows=len(rows) + len(issues),
        created=counts["created"],
        linked=counts["linked"],
        skipped=counts["skipped"],
        failed=len(issues),
        errors=[MemberImportErrorOut(**issue.__dict__) for issue in issues],
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
    _assert_member_in_scope(db, ctx, member)
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

    if body.password and not ctx.can_reset_account_password:
        raise AppError("forbidden", "仅超管可设置会员密码", status_code=403)

    member = Member(
        site_id=ctx.site_id,
        phone=phone,
        name=name,
        face_status=FaceStatus.NOT_ENROLLED.value,
        acquisition_source=(
            AcquisitionSource.MERCHANT.value if link_mid is not None else AcquisitionSource.PLATFORM.value
        ),
        first_merchant_id=link_mid,
        password_hash=hash_password(body.password) if body.password else None,
    )
    db.add(member)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise AppError("conflict", "该手机号已存在于本场地", status_code=409) from exc

    _apply_referrer(db, ctx, member, body, fields_set=set(body.model_fields_set))
    ensure_member_promoter_code(db, member)

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
    """编辑会员姓名与推荐关系。"""
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    _assert_member_in_scope(db, ctx, member)
    fields_set = set(body.model_fields_set)
    if "name" in fields_set:
        if not body.name or not body.name.strip():
            raise AppError("validation_error", "会员姓名不能为空", status_code=422)
        member.name = body.name.strip()
    _apply_referrer(db, ctx, member, body, fields_set=fields_set)
    write_audit(
        db,
        action="member.update",
        target_type="member",
        target_id=member.id,
        summary=f"更新会员档案 {member.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.post("/{member_id}/avatar", response_model=MemberOut)
async def upload_member_avatar(
    member_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """员工为会员上传展示头像。"""
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    _assert_member_in_scope(db, ctx, member)
    saved = await save_upload_file(file, images_only=True)
    member.avatar_url = saved["url"]
    write_audit(
        db,
        action="member.avatar",
        target_type="member",
        target_id=member.id,
        summary=f"更新会员头像 {member.phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.delete("/{member_id}/avatar", response_model=MemberOut)
def clear_member_avatar(
    member_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """员工清除会员展示头像。"""
    ctx.require_permission("member:write")
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    _assert_member_in_scope(db, ctx, member)
    member.avatar_url = None
    write_audit(
        db,
        action="member.avatar_clear",
        target_type="member",
        target_id=member.id,
        summary=f"清除会员头像 {member.phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(member)
    return _member_out(db, member)


@router.post("/{member_id}/password")
def reset_member_password(
    member_id: int,
    body: PasswordResetIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """场地超管可改全部会员密码；业务系统超管仅可改本商户挂靠会员。"""
    ctx.require_password_reset()
    member = db.get(Member, member_id)
    if member is None or member.site_id != ctx.site_id:
        raise AppError("not_found", "会员不存在", status_code=404)
    _assert_member_in_scope(db, ctx, member)
    member.password_hash = hash_password(body.password)
    write_audit(
        db,
        action="member.password_reset",
        target_type="member",
        target_id=member.id,
        summary=f"重置会员登录密码 {member.phone}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=None if ctx.is_site_admin else ctx.merchant_id,
    )
    db.commit()
    return {"ok": True, "has_password": True}


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
