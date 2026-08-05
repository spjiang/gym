"""综合经营 — RBAC 配置 API。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.manifest_sync import sync_role_permissions_from_json
from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import merchant_subsystem_codes
from app.core.errors import AppError
from app.systems.platform.models.identity import Role
from app.systems.platform.models.org import Merchant
from app.systems.platform.models.rbac_catalog import MenuDef, PermissionDef, RoleMenu, RolePermission, Subsystem
from app.systems.platform.services.audit import write_audit

router = APIRouter(prefix="/rbac", tags=["rbac"])


class SubsystemOut(BaseModel):
    code: str
    name: str
    description: str | None
    is_business: bool
    sort_order: int
    is_enabled: bool
    is_deprecated: bool

    model_config = ConfigDict(from_attributes=True)


class SubsystemPatch(BaseModel):
    is_enabled: bool | None = None
    sort_order: int | None = None


class PermissionDefOut(BaseModel):
    code: str
    subsystem_code: str
    name: str
    is_deprecated: bool

    model_config = ConfigDict(from_attributes=True)


class MenuDefOut(BaseModel):
    code: str
    subsystem_code: str
    path: str
    name: str
    required_any: list[str]
    sort_order: int
    is_deprecated: bool

    model_config = ConfigDict(from_attributes=True)


class RoleOut(BaseModel):
    id: int
    code: str
    name: str
    is_site_scope: bool
    merchant_id: int | None
    is_system: bool
    permission_codes: list[str]
    menu_codes: list[str]


class RoleIn(BaseModel):
    code: str = Field(min_length=2, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    merchant_id: int | None = None
    is_site_scope: bool | None = None


class RolePatch(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=128)


class GrantsIn(BaseModel):
    permission_codes: list[str] = Field(default_factory=list)
    menu_codes: list[str] = Field(default_factory=list)


def _role_out(db: Session, role: Role) -> RoleOut:
    perms = list(
        db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).all()
    )
    if not perms:
        perms = list(role.permissions or [])
    menus = list(db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == role.id)).all())
    return RoleOut(
        id=role.id,
        code=role.code,
        name=role.name,
        is_site_scope=role.is_site_scope,
        merchant_id=role.merchant_id,
        is_system=role.is_system,
        permission_codes=perms,
        menu_codes=menus,
    )


def _require_rbac_or_staff(ctx: RequestContext) -> None:
    ctx.require_permission("rbac:manage", "staff:manage")


def _assert_can_edit_role(ctx: RequestContext, role: Role) -> None:
    if ctx.is_site_admin:
        return
    if role.merchant_id is None or role.merchant_id != ctx.merchant_id:
        raise AppError("forbidden", "只能管理本商户角色", status_code=403)
    if role.is_system:
        raise AppError("forbidden", "系统角色不可由商户修改", status_code=403)


def _allowed_permission_codes(db: Session, *, merchant_id: int | None) -> set[str]:
    q = (
        select(PermissionDef.code)
        .join(Subsystem, Subsystem.code == PermissionDef.subsystem_code)
        .where(
            PermissionDef.is_deprecated.is_(False),
            Subsystem.is_enabled.is_(True),
            Subsystem.is_deprecated.is_(False),
        )
    )
    codes = set(db.scalars(q).all())
    if merchant_id is None:
        return codes
    linked = set(merchant_subsystem_codes(db, merchant_id))
    # 商户角色：业态权限 ⊆ 已挂接；platform 非业态权限仍可按需授予（组织/会员/门禁/订单）
    out: set[str] = set()
    for row in db.scalars(select(PermissionDef).where(PermissionDef.is_deprecated.is_(False))).all():
        sub = db.get(Subsystem, row.subsystem_code)
        if sub is None or not sub.is_enabled or sub.is_deprecated:
            continue
        if sub.is_business and row.subsystem_code not in linked:
            continue
        out.add(row.code)
    return out


def _allowed_menu_codes(db: Session, *, merchant_id: int | None) -> set[str]:
    out: set[str] = set()
    linked = set(merchant_subsystem_codes(db, merchant_id)) if merchant_id is not None else None
    for row in db.scalars(select(MenuDef).where(MenuDef.is_deprecated.is_(False))).all():
        sub = db.get(Subsystem, row.subsystem_code)
        if sub is None or not sub.is_enabled or sub.is_deprecated:
            continue
        if linked is not None and sub.is_business and row.subsystem_code not in linked:
            continue
        out.add(row.code)
    return out


@router.get("/subsystems", response_model=list[SubsystemOut])
def list_subsystems(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    rows = list(db.scalars(select(Subsystem).order_by(Subsystem.sort_order, Subsystem.code)).all())
    return rows


@router.patch("/subsystems/{code}", response_model=SubsystemOut)
def patch_subsystem(
    code: str,
    body: SubsystemPatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    if not ctx.is_site_admin:
        raise AppError("forbidden", "仅场地超管可启停子系统", status_code=403)
    row = db.get(Subsystem, code)
    if row is None:
        raise AppError("not_found", "子系统不存在", status_code=404)
    if body.is_enabled is not None:
        row.is_enabled = body.is_enabled
    if body.sort_order is not None:
        row.sort_order = body.sort_order
    write_audit(
        db,
        action="rbac.subsystem_patch",
        target_type="subsystem",
        target_id=0,
        summary=f"{code} enabled={row.is_enabled}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=None,
    )
    db.commit()
    db.refresh(row)
    return row


@router.get("/permission-defs", response_model=list[PermissionDefOut])
def list_permission_defs(
    subsystem: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    q = select(PermissionDef).where(PermissionDef.is_deprecated.is_(False))
    if subsystem:
        q = q.where(PermissionDef.subsystem_code == subsystem)
    return list(db.scalars(q.order_by(PermissionDef.subsystem_code, PermissionDef.code)).all())


@router.get("/menu-defs", response_model=list[MenuDefOut])
def list_menu_defs(
    subsystem: str | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    q = select(MenuDef).where(MenuDef.is_deprecated.is_(False))
    if subsystem:
        q = q.where(MenuDef.subsystem_code == subsystem)
    return list(db.scalars(q.order_by(MenuDef.subsystem_code, MenuDef.sort_order)).all())


@router.get("/roles", response_model=list[RoleOut])
def list_roles(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    q = select(Role)
    if not ctx.is_site_admin:
        q = q.where(Role.merchant_id == ctx.merchant_id)
    rows = list(db.scalars(q.order_by(Role.id)).all())
    return [_role_out(db, r) for r in rows]


@router.get("/roles/assignable", response_model=list[RoleOut])
def list_assignable_roles(
    merchant_id: int | None = None,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    ctx.require_permission("staff:manage")
    q = select(Role)
    if ctx.is_site_admin:
        mid = merchant_id
        if mid is None:
            # 超管未指定：场地级 + 全部商户角色过多时仅返回场地级与请求商户
            q = q.where(Role.merchant_id.is_(None))
        else:
            q = q.where((Role.merchant_id.is_(None)) | (Role.merchant_id == mid))
    else:
        # 商户管理员：仅本商户实例角色（不含场地模板 tpl_*）
        q = q.where(Role.merchant_id == ctx.merchant_id)
    rows = list(db.scalars(q.order_by(Role.id)).all())
    # 不可直接分配角色模板
    rows = [r for r in rows if not r.code.startswith("tpl_")]
    return [_role_out(db, r) for r in rows]


@router.post("/roles", response_model=RoleOut)
def create_role(
    body: RoleIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    code = body.code.strip()
    if ctx.is_site_admin:
        merchant_id = body.merchant_id
        is_site_scope = body.is_site_scope if body.is_site_scope is not None else merchant_id is None
    else:
        merchant_id = ctx.merchant_id
        if merchant_id is None:
            raise AppError("merchant_required", "当前账号未绑定商户", status_code=403)
        is_site_scope = False
        if body.merchant_id is not None and body.merchant_id != merchant_id:
            raise AppError("forbidden", "禁止跨商户创建角色", status_code=403)

    if merchant_id is not None:
        m = db.get(Merchant, merchant_id)
        if m is None or m.site_id != ctx.site_id:
            raise AppError("not_found", "商户不存在", status_code=404)

    exists_q = select(Role).where(Role.code == code)
    if merchant_id is None:
        exists_q = exists_q.where(Role.merchant_id.is_(None))
    else:
        exists_q = exists_q.where(Role.merchant_id == merchant_id)
    if db.scalar(exists_q) is not None:
        raise AppError("duplicate_role", "角色编码已存在", status_code=409)

    role = Role(
        code=code,
        name=body.name.strip(),
        permissions=[],
        is_site_scope=is_site_scope,
        merchant_id=merchant_id,
        is_system=False,
    )
    db.add(role)
    db.flush()
    write_audit(
        db,
        action="rbac.role_create",
        target_type="role",
        target_id=role.id,
        summary=f"创建角色 {role.code}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=merchant_id,
    )
    db.commit()
    db.refresh(role)
    return _role_out(db, role)


@router.patch("/roles/{role_id}", response_model=RoleOut)
def patch_role(
    role_id: int,
    body: RolePatch,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    role = db.get(Role, role_id)
    if role is None:
        raise AppError("not_found", "角色不存在", status_code=404)
    _assert_can_edit_role(ctx, role)
    if body.name is not None:
        role.name = body.name.strip()
    db.commit()
    db.refresh(role)
    return _role_out(db, role)


@router.delete("/roles/{role_id}")
def delete_role(
    role_id: int,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    role = db.get(Role, role_id)
    if role is None:
        raise AppError("not_found", "角色不存在", status_code=404)
    _assert_can_edit_role(ctx, role)
    if role.is_system:
        raise AppError("forbidden", "系统角色不可删除", status_code=403)
    for row in db.scalars(select(RolePermission).where(RolePermission.role_id == role.id)).all():
        db.delete(row)
    for row in db.scalars(select(RoleMenu).where(RoleMenu.role_id == role.id)).all():
        db.delete(row)
    db.delete(role)
    db.commit()
    return {"ok": True}


@router.put("/roles/{role_id}/grants", response_model=RoleOut)
def put_role_grants(
    role_id: int,
    body: GrantsIn,
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    _require_rbac_or_staff(ctx)
    role = db.get(Role, role_id)
    if role is None:
        raise AppError("not_found", "角色不存在", status_code=404)
    _assert_can_edit_role(ctx, role)

    perm_codes = list(dict.fromkeys(body.permission_codes))
    menu_codes = list(dict.fromkeys(body.menu_codes))
    if role.merchant_id is not None and "*" in perm_codes:
        raise AppError("forbidden", "商户角色不能授予 *", status_code=403)

    allowed_perms = _allowed_permission_codes(db, merchant_id=role.merchant_id)
    allowed_menus = _allowed_menu_codes(db, merchant_id=role.merchant_id)
    # 场地级角色可授予 *（仅超管可编辑场地级）
    if role.merchant_id is None:
        allowed_perms = set(allowed_perms) | {"*"}

    bad_p = [p for p in perm_codes if p not in allowed_perms]
    if bad_p:
        raise AppError("forbidden", f"无权授予权限: {', '.join(bad_p)}", status_code=403)
    bad_m = [m for m in menu_codes if m not in allowed_menus]
    if bad_m:
        raise AppError("forbidden", f"无权授予菜单: {', '.join(bad_m)}", status_code=403)

    for row in db.scalars(select(RolePermission).where(RolePermission.role_id == role.id)).all():
        db.delete(row)
    for row in db.scalars(select(RoleMenu).where(RoleMenu.role_id == role.id)).all():
        db.delete(row)
    db.flush()
    for p in perm_codes:
        db.add(RolePermission(role_id=role.id, permission_code=p))
    for m in menu_codes:
        db.add(RoleMenu(role_id=role.id, menu_code=m))
    role.permissions = perm_codes
    write_audit(
        db,
        action="rbac.role_grants",
        target_type="role",
        target_id=role.id,
        summary=f"更新角色授权 perms={len(perm_codes)} menus={len(menu_codes)}",
        actor_staff_id=ctx.staff.id,
        site_id=ctx.site_id,
        merchant_id=role.merchant_id,
    )
    db.commit()
    db.refresh(role)
    return _role_out(db, role)
