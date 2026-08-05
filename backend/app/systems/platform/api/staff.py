"""员工与角色分配。"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.core.db import get_db
from app.core.deps import ROLE_SITE_ADMIN, RequestContext, get_current_context
from app.core.errors import AppError
from app.core.schemas.common import RoleAssignIn, StaffCreateIn, StaffOut
from app.core.schemas.paging import PageOut
from app.core.security import hash_password
from app.systems.platform.models.identity import Role, StaffRole, StaffUser
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/staff", tags=["staff"])


def _to_out(staff: StaffUser) -> StaffOut:
    return StaffOut(
        id=staff.id,
        site_id=staff.site_id,
        merchant_id=staff.merchant_id,
        username=staff.username,
        display_name=staff.display_name,
        is_active=staff.is_active,
        role_codes=[sr.role.code for sr in staff.roles],
    )


def _resolve_roles(db: Session, role_codes: list[str], merchant_id: int | None) -> list[Role]:
    """优先匹配本商户角色实例，否则回落场地级非模板角色。"""
    roles: list[Role] = []
    for code in role_codes:
        if code.startswith("tpl_"):
            raise AppError("invalid_role", "不可直接分配角色模板", status_code=400)
        role = None
        if merchant_id is not None:
            role = db.scalar(select(Role).where(Role.code == code, Role.merchant_id == merchant_id))
        if role is None:
            role = db.scalar(select(Role).where(Role.code == code, Role.merchant_id.is_(None)))
        if role is None:
            raise AppError("invalid_role", f"未知角色: {code}", status_code=400)
        if role.code.startswith("tpl_"):
            raise AppError("invalid_role", "不可直接分配角色模板", status_code=400)
        roles.append(role)
    return roles


@router.get("", response_model=PageOut[StaffOut])
def list_staff(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    q: str | None = None,
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("staff:manage", "org:manage")
    filters = [StaffUser.site_id == ctx.site_id]
    if not ctx.is_site_admin:
        filters.append(StaffUser.merchant_id == ctx.merchant_id)
    elif merchant_id is not None:
        filters.append(StaffUser.merchant_id == merchant_id)
    keyword = (q or "").strip()
    if keyword:
        like = f"%{keyword}%"
        filters.append(or_(StaffUser.username.ilike(like), StaffUser.display_name.ilike(like)))
    total = db.scalar(select(func.count()).select_from(StaffUser).where(*filters)) or 0
    rows = list(
        db.scalars(
            select(StaffUser)
            .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
            .where(*filters)
            .order_by(StaffUser.id)
            .offset((page - 1) * page_size)
            .limit(page_size)
        ).all()
    )
    return PageOut(items=[_to_out(s) for s in rows], total=total, page=page, page_size=page_size)


@router.post("", response_model=StaffOut)
def create_staff(
    body: StaffCreateIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("staff:manage", "org:manage")
    if db.scalar(select(StaffUser).where(StaffUser.username == body.username)):
        raise AppError("conflict", "用户名已存在", status_code=409)

    merchant_id = body.merchant_id
    if ROLE_SITE_ADMIN in body.role_codes:
        if not ctx.is_site_admin:
            raise AppError("forbidden", "不可分配场地超管角色", status_code=403)
        merchant_id = None
    else:
        merchant_id = ctx.resolve_merchant_id(merchant_id)

    roles = _resolve_roles(db, body.role_codes, merchant_id)

    staff = StaffUser(
        site_id=ctx.site_id,
        merchant_id=merchant_id,
        username=body.username,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
        is_active=True,
    )
    db.add(staff)
    db.flush()
    for role in roles:
        db.add(StaffRole(staff_id=staff.id, role_id=role.id))
    write_audit(
        db,
        action="staff.create",
        target_type="staff",
        target_id=staff.id,
        summary=f"创建员工 {staff.username} 角色={body.role_codes}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=merchant_id,
    )
    db.commit()
    staff = db.scalar(
        select(StaffUser)
        .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
        .where(StaffUser.id == staff.id)
    )
    return _to_out(staff)


@router.put("/{staff_id}/roles", response_model=StaffOut)
def assign_roles(
    staff_id: int,
    body: RoleAssignIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("staff:manage", "org:manage")
    staff = db.scalar(
        select(StaffUser)
        .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
        .where(StaffUser.id == staff_id, StaffUser.site_id == ctx.site_id)
    )
    if staff is None:
        raise AppError("not_found", "员工不存在", status_code=404)
    if not ctx.is_site_admin and staff.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "禁止跨商户操作", status_code=403)
    if ROLE_SITE_ADMIN in body.role_codes and not ctx.is_site_admin:
        raise AppError("forbidden", "不可分配场地超管角色", status_code=403)

    roles = _resolve_roles(db, body.role_codes, staff.merchant_id)

    old = sorted(sr.role.code for sr in staff.roles)
    for sr in list(staff.roles):
        db.delete(sr)
    db.flush()
    for role in roles:
        db.add(StaffRole(staff_id=staff.id, role_id=role.id))
    write_audit(
        db,
        action="staff.roles_update",
        target_type="staff",
        target_id=staff.id,
        summary=f"角色变更 {old} -> {sorted(body.role_codes)}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=staff.merchant_id,
    )
    db.commit()
    staff = db.scalar(
        select(StaffUser)
        .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
        .where(StaffUser.id == staff_id)
    )
    return _to_out(staff)
