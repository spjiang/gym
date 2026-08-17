"""将各子系统 manifest 同步到库内能力目录，并补齐系统角色菜单。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.systems.platform.models.identity import Role
from app.systems.platform.models.rbac_catalog import MenuDef, PermissionDef, RoleMenu, RolePermission, Subsystem
from app.systems.platform.services.role_packs import sync_existing_role_packs
from app.systems import iter_system_manifests


def _perm_match(role_perms: set[str], required_any: list[str]) -> bool:
    """角色是否满足菜单/能力的 required_any。

    - 角色持有 ``*``：匹配全部
    - ``required_any`` 中的 ``*`` 仅表示「超管通配」，不对普通角色开放
    """
    if "*" in role_perms:
        return True
    return any(p in role_perms for p in required_any if p != "*")


def sync_manifests(db: Session, *, ensure_role_menus: bool = True) -> None:
    """幂等 upsert 子系统/权限/菜单；可选为已有角色补菜单授予。"""
    manifests = iter_system_manifests()
    seen_systems: set[str] = set()
    seen_perms: set[str] = set()
    seen_menus: set[str] = set()

    # 先落子系统行，满足外键
    for m in manifests:
        code = m["code"]
        seen_systems.add(code)
        row = db.get(Subsystem, code)
        if row is None:
            row = Subsystem(
                code=code,
                name=m["name"],
                description=m.get("description"),
                is_business=bool(m.get("is_business")),
                sort_order=int(m.get("sort_order") or 0),
                is_enabled=True,
                is_deprecated=False,
            )
            db.add(row)
        else:
            row.name = m["name"]
            row.description = m.get("description")
            row.is_business = bool(m.get("is_business"))
            row.sort_order = int(m.get("sort_order") or 0)
            row.is_deprecated = False
    db.flush()

    for m in manifests:
        code = m["code"]
        for p in m.get("permissions") or []:
            pcode = p["code"]
            seen_perms.add(pcode)
            prow = db.get(PermissionDef, pcode)
            if prow is None:
                db.add(
                    PermissionDef(
                        code=pcode,
                        subsystem_code=code,
                        name=p["name"],
                        is_deprecated=False,
                    )
                )
            else:
                prow.subsystem_code = code
                prow.name = p["name"]
                prow.is_deprecated = False

        for menu in m.get("menus") or []:
            mcode = menu["code"]
            seen_menus.add(mcode)
            mrow = db.get(MenuDef, mcode)
            if mrow is None:
                db.add(
                    MenuDef(
                        code=mcode,
                        subsystem_code=code,
                        path=menu["path"],
                        name=menu["name"],
                        required_any=list(menu.get("required_any") or []),
                        sort_order=int(menu.get("sort_order") or 0),
                        is_deprecated=False,
                    )
                )
            else:
                mrow.subsystem_code = code
                mrow.path = menu["path"]
                mrow.name = menu["name"]
                mrow.required_any = list(menu.get("required_any") or [])
                mrow.sort_order = int(menu.get("sort_order") or 0)
                mrow.is_deprecated = False

    for row in db.scalars(select(Subsystem)).all():
        if row.code not in seen_systems:
            row.is_deprecated = True
    for row in db.scalars(select(PermissionDef)).all():
        if row.code not in seen_perms:
            row.is_deprecated = True
    for row in db.scalars(select(MenuDef)).all():
        if row.code not in seen_menus:
            row.is_deprecated = True

    db.flush()

    if ensure_role_menus:
        _ensure_role_menus_from_permissions(db)
        # 模板菜单更新后，补到已有商户角色包（只增不删）
        sync_existing_role_packs(db)
        # 排课菜单收窄为 course:manage 后，收回前台角色上的旧授予
        _revoke_schedule_menu_without_manage(db)

    db.flush()


def _role_permission_set(db: Session, role: Role) -> set[str]:
    rows = list(
        db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).all()
    )
    if rows:
        return set(rows)
    return set(role.permissions or [])


def _ensure_role_menus_from_permissions(db: Session) -> None:
    """按权限为角色装配菜单。

    - 场地级模板角色（merchant_id 为空）：每次按权限重算（便于种子与权限增量）
    - 商户自定义角色：仅在尚无任何菜单时首次补齐，避免覆盖人工微调
    """
    menus = list(db.scalars(select(MenuDef).where(MenuDef.is_deprecated.is_(False))).all())
    roles = list(db.scalars(select(Role)).all())
    for role in roles:
        is_template = role.merchant_id is None
        existing_rows = list(db.scalars(select(RoleMenu).where(RoleMenu.role_id == role.id)).all())
        if not is_template and existing_rows:
            continue

        perms = _role_permission_set(db, role)
        wanted: set[str] = set()
        for menu in menus:
            if not _perm_match(perms, list(menu.required_any or [])):
                continue
            # 业务/子系统菜单须具备对应 system:xxx，避免公共权限串菜单
            # 业务子系统菜单须具备 system:xxx；综合经营菜单按 required_any 即可
            if menu.subsystem_code in ("gym", "catering"):
                if "*" not in perms and f"system:{menu.subsystem_code}" not in perms:
                    continue
            wanted.add(menu.code)

        existing = {r.menu_code for r in existing_rows}
        for code in wanted - existing:
            db.add(RoleMenu(role_id=role.id, menu_code=code))
        if is_template:
            for row in existing_rows:
                if row.menu_code not in wanted:
                    db.delete(row)


def _revoke_schedule_menu_without_manage(db: Session) -> None:
    """无排课权限的角色不再保留「团课排课」菜单。"""
    roles = list(db.scalars(select(Role)).all())
    for role in roles:
        perms = _role_permission_set(db, role)
        if "*" in perms or "course:manage" in perms:
            continue
        stale = list(
            db.scalars(
                select(RoleMenu).where(
                    RoleMenu.role_id == role.id,
                    RoleMenu.menu_code == "gym.group_courses",
                )
            ).all()
        )
        for row in stale:
            db.delete(row)


def sync_role_permissions_from_json(db: Session, role: Role) -> None:
    """把角色 JSON permissions 同步到 role_permissions（幂等）。"""
    existing = set(
        db.scalars(select(RolePermission.permission_code).where(RolePermission.role_id == role.id)).all()
    )
    wanted = set(role.permissions or [])
    for p in wanted - existing:
        db.add(RolePermission(role_id=role.id, permission_code=p))
    for p in existing - wanted:
        row = db.scalar(
            select(RolePermission).where(
                RolePermission.role_id == role.id, RolePermission.permission_code == p
            )
        )
        if row is not None:
            db.delete(row)
