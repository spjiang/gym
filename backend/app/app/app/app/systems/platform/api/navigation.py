"""综合经营 — 登录导航裁剪。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.deps import RequestContext, get_current_context
from app.core.domain.subsystems import merchant_subsystem_codes
from app.systems.platform.models.rbac_catalog import MenuDef, RoleMenu, Subsystem

router = APIRouter(tags=["navigation"])


class NavSubsystem(BaseModel):
    code: str
    name: str
    description: str | None
    is_business: bool
    sort_order: int
    entry_path: str | None = None

    model_config = ConfigDict(from_attributes=True)


class NavMenu(BaseModel):
    code: str
    subsystem_code: str
    path: str
    name: str
    sort_order: int

    model_config = ConfigDict(from_attributes=True)


class NavigationOut(BaseModel):
    subsystems: list[NavSubsystem]
    menus: list[NavMenu]


def _entry_path(db: Session, subsystem_code: str) -> str | None:
    row = db.scalar(
        select(MenuDef)
        .where(
            MenuDef.subsystem_code == subsystem_code,
            MenuDef.is_deprecated.is_(False),
        )
        .order_by(MenuDef.sort_order, MenuDef.code)
    )
    return row.path if row else None


@router.get("/me/navigation", response_model=NavigationOut)
def my_navigation(
    db: Session = Depends(get_db),
    ctx: RequestContext = Depends(get_current_context),
):
    # 超管：全部启用子系统 + 全部未废弃菜单
    if "*" in ctx.permissions or ctx.is_site_admin:
        subs = list(
            db.scalars(
                select(Subsystem)
                .where(Subsystem.is_enabled.is_(True), Subsystem.is_deprecated.is_(False))
                .order_by(Subsystem.sort_order)
            ).all()
        )
        menus = list(
            db.scalars(
                select(MenuDef)
                .join(Subsystem, Subsystem.code == MenuDef.subsystem_code)
                .where(
                    MenuDef.is_deprecated.is_(False),
                    Subsystem.is_enabled.is_(True),
                    Subsystem.is_deprecated.is_(False),
                )
                .order_by(MenuDef.subsystem_code, MenuDef.sort_order)
            ).all()
        )
        return NavigationOut(
            subsystems=[
                NavSubsystem(
                    code=s.code,
                    name=s.name,
                    description=s.description,
                    is_business=s.is_business,
                    sort_order=s.sort_order,
                    entry_path=_entry_path(db, s.code),
                )
                for s in subs
            ],
            menus=[
                NavMenu(
                    code=m.code,
                    subsystem_code=m.subsystem_code,
                    path=m.path,
                    name=m.name,
                    sort_order=m.sort_order,
                )
                for m in menus
            ],
        )

    # 角色菜单并集
    role_ids = [sr.role_id for sr in ctx.staff.roles]
    menu_codes: set[str] = set()
    if role_ids:
        menu_codes = set(
            db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id.in_(role_ids))).all()
        )

    linked = set(merchant_subsystem_codes(db, ctx.merchant_id)) if ctx.merchant_id else set()

    menus_out: list[NavMenu] = []
    sub_codes: set[str] = set()
    for m in db.scalars(select(MenuDef).where(MenuDef.is_deprecated.is_(False))).all():
        if m.code not in menu_codes:
            continue
        sub = db.get(Subsystem, m.subsystem_code)
        if sub is None or not sub.is_enabled or sub.is_deprecated:
            continue
        if sub.is_business and ctx.merchant_id is not None and m.subsystem_code not in linked:
            continue
        sub_codes.add(m.subsystem_code)
        menus_out.append(
            NavMenu(
                code=m.code,
                subsystem_code=m.subsystem_code,
                path=m.path,
                name=m.name,
                sort_order=m.sort_order,
            )
        )

    # platform 始终可出现在子系统卡片（若有任意 platform 菜单）
    subs_out: list[NavSubsystem] = []
    for s in db.scalars(
        select(Subsystem)
        .where(Subsystem.is_enabled.is_(True), Subsystem.is_deprecated.is_(False))
        .order_by(Subsystem.sort_order)
    ).all():
        if s.code not in sub_codes:
            continue
        if s.is_business and ctx.merchant_id is not None and s.code not in linked:
            continue
        subs_out.append(
            NavSubsystem(
                code=s.code,
                name=s.name,
                description=s.description,
                is_business=s.is_business,
                sort_order=s.sort_order,
                entry_path=_entry_path(db, s.code),
            )
        )

    menus_out.sort(key=lambda x: (x.subsystem_code, x.sort_order, x.code))
    return NavigationOut(subsystems=subs_out, menus=menus_out)
