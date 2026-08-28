"""商户类型、商户与业态子系统关联。"""

import re

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.member_web_url import member_h5_path_url
from app.core.domain.subsystems import (
    DEFAULT_SYSTEMS_BY_MERCHANT_TYPE,
    SYSTEM_CATALOG,
    merchant_subsystem_codes,
    replace_merchant_subsystems,
)
from app.core.errors import AppError
from app.core.upload_urls import is_stored_image_url
from app.systems.platform.models.org import Merchant, MerchantContact, MerchantStatus, MerchantType
from app.core.schemas.common import (
    MerchantContactIn,
    MerchantContactOut,
    MerchantIn,
    MerchantOut,
    MerchantPatch,
    MerchantSubsystemsIn,
    MerchantTypeIn,
    MerchantTypeOut,
    MerchantTypePatch,
)
from app.systems.platform.services.audit import write_audit
from app.systems.platform.services.merchant_lease import lease_metrics

CONTACT_KINDS = {"primary", "emergency", "other"}
CREDIT_CODE_RE = re.compile(r"^[0-9A-Z]{18}$")
MAX_GALLERY_IMAGES = 9
PROFILE_FIELDS = (
    "legal_name",
    "license_no",
    "license_image_url",
    "legal_person",
    "registered_address",
    "business_address",
    "contact_phone",
    "business_hours",
    "description",
    "tagline",
)

router = APIRouter(tags=["organization"])


class SubsystemCatalogOut(BaseModel):
    code: str
    name: str
    short_name: str
    description: str
    permission: str
    is_business: bool


def _opt(value: str | None) -> str | None:
    if value is None:
        return None
    text = value.strip()
    return text or None


def _validate_credit_code(value: str | None) -> str | None:
    code = _opt(value)
    if code is None:
        return None
    code = code.upper()
    if not CREDIT_CODE_RE.fullmatch(code):
        raise AppError("invalid_credit_code", "统一社会信用代码应为 18 位字母或数字", status_code=400)
    return code


def _validate_email(value: str | None) -> str | None:
    email = _opt(value)
    if email is None:
        return None
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        raise AppError("invalid_email", "邮箱格式不正确", status_code=400)
    return email


def _normalize_store_image(url: str | None, *, field: str) -> str | None:
    text = _opt(url)
    if text is None:
        return None
    if not is_stored_image_url(text):
        raise AppError("invalid_image", f"{field}地址无效，请通过系统上传", status_code=400)
    return text


def _normalize_gallery(urls: list[str] | None) -> list[str]:
    """店铺环境图只接受本系统上传地址，去重且最多 9 张。"""
    out: list[str] = []
    for raw in urls or []:
        url = _normalize_store_image(raw, field="环境图")
        if url and url not in out:
            out.append(url)
    if len(out) > MAX_GALLERY_IMAGES:
        raise AppError("too_many_images", "环境图最多 9 张", status_code=400)
    return out


def _replace_contacts(db: Session, merchant_id: int, contacts: list[MerchantContactIn] | None) -> None:
    if contacts is None:
        return
    db.execute(delete(MerchantContact).where(MerchantContact.merchant_id == merchant_id))
    for index, item in enumerate(contacts):
        kind = (item.kind or "other").strip()
        if kind not in CONTACT_KINDS:
            raise AppError("invalid_contact", "联系人类型无效", status_code=400)
        name = item.name.strip()
        phone = item.phone.strip()
        if not name or not phone:
            raise AppError("invalid_contact", "联系人姓名与电话必填", status_code=400)
        db.add(
            MerchantContact(
                merchant_id=merchant_id,
                name=name,
                phone=phone,
                title=_opt(item.title),
                kind=kind,
                remark=_opt(item.remark),
                sort_order=item.sort_order or index,
            )
        )


def _apply_lease(row: Merchant, payload: dict) -> None:
    """写入租赁起止日；结束日不得早于开始日。"""
    if "lease_starts_on" not in payload and "lease_ends_on" not in payload:
        return
    starts = payload["lease_starts_on"] if "lease_starts_on" in payload else row.lease_starts_on
    ends = payload["lease_ends_on"] if "lease_ends_on" in payload else row.lease_ends_on
    if starts and ends and ends < starts:
        raise AppError("invalid_lease", "租赁结束日不能早于开始日", status_code=400)
    if "lease_starts_on" in payload:
        row.lease_starts_on = starts
    if "lease_ends_on" in payload:
        row.lease_ends_on = ends


def _apply_profile(row: Merchant, payload: dict) -> None:
    if "credit_code" in payload:
        row.credit_code = _validate_credit_code(payload.get("credit_code"))
    if "contact_email" in payload:
        row.contact_email = _validate_email(payload.get("contact_email"))
    for field in PROFILE_FIELDS:
        if field in payload:
            value = payload.get(field)
            setattr(row, field, _opt(value) if isinstance(value, str) else value)
    if "cover_image_url" in payload:
        row.cover_image_url = _normalize_store_image(payload.get("cover_image_url"), field="封面图")
    if "gallery_image_urls" in payload:
        row.gallery_image_urls = _normalize_gallery(payload.get("gallery_image_urls"))
    _apply_lease(row, payload)


def _merchant_contacts(db: Session, merchant_id: int) -> list[MerchantContact]:
    return list(
        db.scalars(
            select(MerchantContact)
            .where(MerchantContact.merchant_id == merchant_id)
            .order_by(MerchantContact.sort_order, MerchantContact.id)
        ).all()
    )


def _merchant_out(db: Session, row: Merchant) -> MerchantOut:
    contacts = _merchant_contacts(db, row.id)
    return MerchantOut(
        id=row.id,
        site_id=row.site_id,
        merchant_type_id=row.merchant_type_id,
        name=row.name,
        status=row.status,
        created_at=row.created_at,
        subsystem_codes=merchant_subsystem_codes(db, row.id),
        legal_name=row.legal_name,
        credit_code=row.credit_code,
        license_no=row.license_no,
        license_image_url=row.license_image_url,
        legal_person=row.legal_person,
        registered_address=row.registered_address,
        business_address=row.business_address,
        contact_phone=row.contact_phone,
        contact_email=row.contact_email,
        business_hours=row.business_hours,
        description=row.description,
        tagline=row.tagline,
        cover_image_url=row.cover_image_url,
        gallery_image_urls=list(row.gallery_image_urls or []),
        lease_starts_on=row.lease_starts_on,
        lease_ends_on=row.lease_ends_on,
        **lease_metrics(row.lease_starts_on, row.lease_ends_on),
        contacts=[MerchantContactOut.model_validate(c) for c in contacts],
        has_license=bool(row.credit_code or row.license_no or row.license_image_url),
        emergency_contact_count=sum(1 for c in contacts if c.kind == "emergency"),
    )


def _assert_can_edit_profile(ctx: RequestContext, row: Merchant) -> None:
    if ctx.is_site_admin:
        return
    if ctx.merchant_id == row.id and "staff:manage" in ctx.permissions:
        return
    raise AppError("forbidden", "无权编辑该商户档案", status_code=403)


@router.get("/subsystems", response_model=list[SubsystemCatalogOut])
def list_subsystems(ctx: RequestContext = Depends(get_current_context)):
    """子系统目录（供创建商户勾选与门户展示）。"""
    ctx.require_permission("org:read", "org:manage", "order:read", "*")
    return [
        SubsystemCatalogOut(
            code=v["code"],
            name=v["name"],
            short_name=v["short_name"],
            description=v["description"],
            permission=v["permission"],
            is_business=v["code"] in {"gym", "catering"},
        )
        for v in SYSTEM_CATALOG.values()
    ]


@router.get("/merchant-types", response_model=list[MerchantTypeOut])
def list_merchant_types(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("org:read", "org:manage")
    return list(db.scalars(select(MerchantType).order_by(MerchantType.id)).all())


@router.post("/merchant-types", response_model=MerchantTypeOut)
def create_merchant_type(
    body: MerchantTypeIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可管理商户类型", status_code=403)
    exists = db.scalar(select(MerchantType).where(MerchantType.code == body.code))
    if exists:
        raise AppError("conflict", "商户类型编码已存在", status_code=409)
    row = MerchantType(code=body.code, name=body.name, description=body.description)
    db.add(row)
    db.flush()
    write_audit(
        db,
        action="merchant_type.create",
        target_type="merchant_type",
        target_id=row.id,
        summary=f"创建商户类型 {row.code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.patch("/merchant-types/{type_id}", response_model=MerchantTypeOut)
def update_merchant_type(
    type_id: int,
    body: MerchantTypePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可管理商户类型", status_code=403)
    row = db.get(MerchantType, type_id)
    if row is None:
        raise AppError("not_found", "商户类型不存在", status_code=404)
    if body.code is not None:
        code = body.code.strip()
        clash = db.scalar(select(MerchantType).where(MerchantType.code == code, MerchantType.id != type_id))
        if clash:
            raise AppError("conflict", "商户类型编码已存在", status_code=409)
        row.code = code
    if body.name is not None:
        row.name = body.name.strip()
    if body.description is not None:
        row.description = body.description.strip() or None
    write_audit(
        db,
        action="merchant_type.update",
        target_type="merchant_type",
        target_id=row.id,
        summary=f"更新商户类型 {row.code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/merchants", response_model=list[MerchantOut])
def list_merchants(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """商户列表。

    - 超管：本场地全部
    - 有组织读权限：未绑商户看全场；已绑商户看本商户
    - 其余已绑商户员工（教练/前台等）：仅本商户，无需 org:read
    """
    q = select(Merchant).where(Merchant.site_id == ctx.site_id)

    if ctx.is_site_admin or "*" in ctx.permissions:
        pass
    elif "org:read" in ctx.permissions or "org:manage" in ctx.permissions:
        if ctx.merchant_id is not None:
            q = q.where(Merchant.id == ctx.merchant_id)
    elif ctx.merchant_id is not None:
        q = q.where(Merchant.id == ctx.merchant_id)
    else:
        raise AppError("forbidden", "权限不足", status_code=403)

    rows = list(db.scalars(q.order_by(Merchant.id)).all())
    return [_merchant_out(db, row) for row in rows]


@router.get("/merchants/{merchant_id}", response_model=MerchantOut)
def get_merchant(
    merchant_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    row = db.get(Merchant, merchant_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    if not ctx.is_site_admin and ctx.merchant_id is not None and row.id != ctx.merchant_id:
        raise AppError("forbidden", "无权查看该商户", status_code=403)
    return _merchant_out(db, row)


@router.post("/merchants", response_model=MerchantOut)
def create_merchant(
    body: MerchantIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可创建商户", status_code=403)
    site_id = body.site_id or ctx.site_id
    mt = db.get(MerchantType, body.merchant_type_id)
    if mt is None:
        raise AppError("not_found", "商户类型不存在", status_code=404)
    if body.status not in {s.value for s in MerchantStatus}:
        raise AppError("invalid_status", "非法商户状态", status_code=400)
    if not body.name.strip():
        raise AppError("validation_error", "商户名称不能为空", status_code=422)

    codes = body.subsystem_codes
    if not codes:
        codes = DEFAULT_SYSTEMS_BY_MERCHANT_TYPE.get(mt.code, ["gym"])

    row = Merchant(
        site_id=site_id,
        merchant_type_id=body.merchant_type_id,
        name=body.name.strip(),
        status=body.status,
    )
    _apply_profile(row, body.model_dump(exclude_unset=True))
    db.add(row)
    db.flush()
    _replace_contacts(db, row.id, body.contacts)
    linked = replace_merchant_subsystems(db, row.id, codes)
    from app.systems.platform.services.role_packs import ensure_merchant_role_packs

    ensure_merchant_role_packs(db, row.id)
    write_audit(
        db,
        action="merchant.create",
        target_type="merchant",
        target_id=row.id,
        summary=f"创建商户 {row.name}，子系统 {','.join(linked)}",
        actor_staff_id=ctx.staff.id,
        site_id=site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _merchant_out(db, row)


@router.put("/merchants/{merchant_id}/subsystems", response_model=MerchantOut)
def update_merchant_subsystems(
    merchant_id: int,
    body: MerchantSubsystemsIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可调整商户子系统", status_code=403)
    row = db.get(Merchant, merchant_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    linked = replace_merchant_subsystems(db, row.id, body.subsystem_codes)
    from app.systems.platform.services.role_packs import ensure_merchant_role_packs

    ensure_merchant_role_packs(db, row.id)
    write_audit(
        db,
        action="merchant.subsystems_update",
        target_type="merchant",
        target_id=row.id,
        summary=f"更新商户子系统为 {','.join(linked)}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _merchant_out(db, row)


@router.get("/merchants/{merchant_id}/acquisition-link")
def merchant_acquisition_link(
    merchant_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """商户获客 H5 链接（供二维码）。"""
    ctx.require_permission("org:read", "org:manage", "*")
    mid = ctx.resolve_merchant_id(merchant_id) if ctx.merchant_id is not None else merchant_id
    if not ctx.is_site_admin and "*" not in ctx.permissions and ctx.merchant_id is not None:
        if mid != ctx.merchant_id:
            raise AppError("forbidden", "只能查看本商户获客码", status_code=403)
    row = db.get(Merchant, mid)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    return {"merchant_id": mid, "url": member_h5_path_url("/login", query={"merchant_id": mid})}


@router.get("/merchants/{merchant_id}/order-types")
def merchant_order_types(
    merchant_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """返回该商户当前业态允许的线下订单类型。"""
    ctx.require_permission("order:read", "order:write")
    mid = ctx.resolve_merchant_id(merchant_id)
    row = db.get(Merchant, mid)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    from app.core.domain.subsystems import ORDER_TYPE_LABELS, allowed_order_types_for_merchant

    allowed = sorted(allowed_order_types_for_merchant(db, mid))
    return [{"value": t, "label": ORDER_TYPE_LABELS.get(t, t)} for t in allowed]


@router.patch("/merchants/{merchant_id}", response_model=MerchantOut)
def update_merchant(
    merchant_id: int,
    body: MerchantPatch | None = None,
    status: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    """编辑商户字段；兼容旧调用 PATCH ?status=。场地超管可改组织项，业务超管可改本店档案。"""
    row = db.get(Merchant, merchant_id)
    if row is None or row.site_id != ctx.site_id:
        raise AppError("not_found", "商户不存在", status_code=404)
    _assert_can_edit_profile(ctx, row)

    data = body.model_dump(exclude_unset=True) if body else {}
    if not ctx.is_site_admin:
        for key in ("merchant_type_id", "status", "subsystem_codes", "lease_starts_on", "lease_ends_on"):
            data.pop(key, None)
        if status is not None:
            raise AppError("forbidden", "仅场地超管可调整商户状态", status_code=403)

    next_status = data.get("status", status if ctx.is_site_admin else None)
    if next_status is not None:
        if next_status not in {s.value for s in MerchantStatus}:
            raise AppError("invalid_status", "非法商户状态", status_code=400)
        row.status = next_status
    if data.get("name") is not None:
        name = str(data["name"]).strip()
        if not name:
            raise AppError("validation_error", "商户名称不能为空", status_code=422)
        row.name = name
    if data.get("merchant_type_id") is not None:
        mt = db.get(MerchantType, data["merchant_type_id"])
        if mt is None:
            raise AppError("not_found", "商户类型不存在", status_code=404)
        row.merchant_type_id = mt.id
    if data.get("subsystem_codes") is not None:
        codes = data["subsystem_codes"]
        if not codes:
            raise AppError("validation_error", "请至少关联一个业态子系统", status_code=422)
        replace_merchant_subsystems(db, row.id, codes)
        from app.systems.platform.services.role_packs import ensure_merchant_role_packs

        ensure_merchant_role_packs(db, row.id)
    _apply_profile(row, data)
    if "contacts" in data:
        _replace_contacts(db, row.id, body.contacts if body else None)

    write_audit(
        db,
        action="merchant.update",
        target_type="merchant",
        target_id=row.id,
        summary=f"更新商户 {row.name}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=row.id,
    )
    db.commit()
    db.refresh(row)
    return _merchant_out(db, row)
