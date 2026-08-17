"""业态角色模板 → 商户角色实例（A+B）。

场地级维护 tpl_* 标准包；商户挂接子系统后幂等复制为本商户实例。
已存在的实例不覆盖权限与菜单，尊重商户微调。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.domain.subsystems import merchant_subsystem_codes
from app.systems.platform.models.identity import Role
from app.systems.platform.models.rbac_catalog import RoleMenu, RolePermission

# (模板 code, 实例 code)
PACK_BY_SYSTEM: dict[str, list[tuple[str, str]]] = {
    "gym": [
        ("tpl_gym_admin", "gym_admin"),
        ("tpl_gym_ops", "gym_ops"),
        ("tpl_gym_coach", "gym_coach"),
    ],
    "catering": [
        ("tpl_bar_admin", "bar_admin"),
        ("tpl_bar_ops", "bar_ops"),
        ("tpl_bar_cashier", "bar_cashier"),
    ],
}


def is_role_template(code: str) -> bool:
    return code.startswith("tpl_")


def ensure_merchant_role_packs(db: Session, merchant_id: int) -> list[int]:
    """按商户已挂子系统复制缺失的角色实例；已存在则跳过。"""
    linked = set(merchant_subsystem_codes(db, merchant_id))
    result_ids: list[int] = []
    for system, pairs in PACK_BY_SYSTEM.items():
        if system not in linked:
            continue
        for tpl_code, inst_code in pairs:
            existing = db.scalar(
                select(Role).where(Role.merchant_id == merchant_id, Role.code == inst_code)
            )
            if existing is not None:
                result_ids.append(existing.id)
                continue
            tpl = db.scalar(select(Role).where(Role.merchant_id.is_(None), Role.code == tpl_code))
            if tpl is None:
                continue
            # 优先用模板已展开的 grants；若尚未同步则回落 JSON
            perm_codes = list(
                db.scalars(
                    select(RolePermission.permission_code).where(RolePermission.role_id == tpl.id)
                ).all()
            )
            if not perm_codes:
                perm_codes = list(tpl.permissions or [])
            menu_codes = list(
                db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == tpl.id)).all()
            )
            inst = Role(
                code=inst_code,
                name=tpl.name,
                permissions=list(perm_codes),
                is_site_scope=False,
                merchant_id=merchant_id,
                is_system=False,
            )
            db.add(inst)
            db.flush()
            for p in perm_codes:
                db.add(RolePermission(role_id=inst.id, permission_code=p))
            for m in menu_codes:
                db.add(RoleMenu(role_id=inst.id, menu_code=m))
            db.flush()
            result_ids.append(inst.id)
    return result_ids


def sync_existing_role_packs(db: Session) -> None:
    """把模板新增的菜单/权限补到已有商户实例，不删除商户已微调的授予。"""
    for _system, pairs in PACK_BY_SYSTEM.items():
        for tpl_code, inst_code in pairs:
            tpl = db.scalar(select(Role).where(Role.merchant_id.is_(None), Role.code == tpl_code))
            if tpl is None:
                continue
            tpl_menus = set(
                db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == tpl.id)).all()
            )
            tpl_perms = set(
                db.scalars(
                    select(RolePermission.permission_code).where(RolePermission.role_id == tpl.id)
                ).all()
            )
            instances = list(
                db.scalars(select(Role).where(Role.code == inst_code, Role.merchant_id.is_not(None))).all()
            )
            for inst in instances:
                have_menus = set(
                    db.scalars(select(RoleMenu.menu_code).where(RoleMenu.role_id == inst.id)).all()
                )
                for menu_code in tpl_menus - have_menus:
                    db.add(RoleMenu(role_id=inst.id, menu_code=menu_code))
                have_perms = set(
                    db.scalars(
                        select(RolePermission.permission_code).where(RolePermission.role_id == inst.id)
                    ).all()
                )
                for perm_code in tpl_perms - have_perms:
                    db.add(RolePermission(role_id=inst.id, permission_code=perm_code))
            db.flush()
