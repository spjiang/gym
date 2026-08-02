"""员工与角色分配。"""

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.deps import ROLE_SITE_ADMIN, RequestContext, get_current_context
from app.errors import AppError
from app.models.identity import Role, StaffRole, StaffUser
from app.schemas.common import RoleAssignIn, StaffCreateIn, StaffOut
from app.security import hash_password
from app.services.audit import write_audit

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


@router.get("", response_model=list[StaffOut])
def list_staff(db: Session = Depends(get_db), ctx: RequestContext = Depends(get_current_context)):
    ctx.require_permission("staff:manage", "org:manage")
    q = (
        select(StaffUser)
        .options(selectinload(StaffUser.roles).selectinload(StaffRole.role))
        .where(StaffUser.site_id == ctx.site_id)
    )
    if not ctx.is_site_admin:
        q = q.where(StaffUser.merchant_id == ctx.merchant_id)
    return [_to_out(s) for s in db.scalars(q.order_by(StaffUser.id)).all()]


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

    roles = list(db.scalars(select(Role).where(Role.code.in_(body.role_codes))).all())
    if len(roles) != len(set(body.role_codes)):
        raise AppError("invalid_role", "存在未知角色", status_code=400)

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

    roles = list(db.scalars(select(Role).where(Role.code.in_(body.role_codes))).all())
    if len(roles) != len(set(body.role_codes)):
        raise AppError("invalid_role", "存在未知角色", status_code=400)

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
