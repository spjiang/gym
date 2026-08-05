# 场地/商户角色包（A+B）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 落地 A+B 角色模型：场地角色 + 业态 `tpl_*` 模板；商户挂接子系统时幂等复制为本商户角色实例；演示账号与登录切换按组织角色命名。

**Architecture:** 在 `systems/platform/services/role_packs.py` 实现 `ensure_merchant_role_packs`；`replace_merchant_subsystems` / seed 调用之。`ROLE_DEFS` 改为 `site_admin`/`site_ops` + 六个 `tpl_*`；员工绑商户实例角色。Assignable 排除 `tpl_*`。前端登录芯片改文案与账号表。

**Tech Stack:** FastAPI · SQLAlchemy 2 · pytest · Vue 3 · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-04-merchant-role-packs-design.md`

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 模板变更不回溯覆盖已有商户实例（仅缺失则创建）
- 商户角色 grants ⊆ 启用目录 ∩ 已挂业态；禁止 `*`
- 用 `code.startswith("tpl_")` 识别模板，**本切片不加** `is_template` 列（YAGNI）
- 未要求不 git commit
- 验证：相关 pytest + Docker 冒烟登录/导航

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/systems/platform/services/role_packs.py` | 新建：模板→实例复制、`ensure_merchant_role_packs` |
| `backend/app/core/domain/subsystems.py` | `replace_merchant_subsystems` 末尾调用复制 |
| `backend/app/seed.py` | 重写 `ROLE_DEFS`；seed 后对 gym/bar 调复制；废弃旧 code |
| `backend/app/seed_demo.py` | 演示账号与绑商户实例角色 |
| `backend/app/systems/platform/api/rbac.py` | assignable/list 排除 `tpl_*`（商户侧）；超管可见模板 |
| `backend/app/systems/platform/api/staff.py` | `_resolve_roles` 禁止绑 `tpl_*` |
| `backend/app/core/deps.py` | `ROLE_COACH` 等常量对齐 `gym_coach` |
| `backend/app/systems/gym/api/course.py` | 教练身份判断兼容 `gym_coach` |
| `backend/tests/test_role_packs.py` | 新建：复制幂等、子系统钩子 |
| `backend/tests/test_org_identity.py` 等 | `role_codes` 改为新 code |
| `frontend/src/core/views/LoginView.vue` | 快速切换芯片 |
| `user.md` / `README.md` | 账号表 |
| Spec 状态行 | 改为已落地 |

---

### Task 1: `ensure_merchant_role_packs` + 失败测试

**Files:**
- Create: `backend/app/systems/platform/services/role_packs.py`
- Create: `backend/tests/test_role_packs.py`
- Modify: `backend/app/core/domain/subsystems.py`

**Interfaces:**
- Produces: `PACK_BY_SYSTEM: dict[str, list[tuple[str, str]]]` 映射 `gym`→`(tpl_gym_admin, gym_admin)` 等
- Produces: `def ensure_merchant_role_packs(db: Session, merchant_id: int) -> list[int]` 返回新建或已存在的实例 role id 列表
- Consumes: `Role`, `RolePermission`, `RoleMenu`, `merchant_subsystem_codes`

- [x] **Step 1: 写失败测试**

```python
# backend/tests/test_role_packs.py
def test_ensure_packs_creates_gym_roles(client, admin_headers, db_session):
    # 前置：seed 已有 tpl_*；创建一个只挂 gym 的商户（或用现有 gym）
    from app.systems.platform.services.role_packs import ensure_merchant_role_packs
    from app.systems.platform.models.identity import Role
    from sqlalchemy import select

    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    ensure_merchant_role_packs(db_session, gym_id)
    db_session.commit()
    codes = set(
        db_session.scalars(
            select(Role.code).where(Role.merchant_id == gym_id)
        ).all()
    )
    assert {"gym_admin", "gym_ops", "gym_coach"} <= codes

def test_ensure_packs_idempotent_keeps_grants(client, admin_headers, db_session):
    from app.systems.platform.services.role_packs import ensure_merchant_role_packs
    from app.systems.platform.models.identity import Role
    from app.systems.platform.models.rbac_catalog import RolePermission
    from sqlalchemy import select

    gym_id = client.get("/api/v1/merchants", headers=admin_headers).json()[0]["id"]
    ensure_merchant_role_packs(db_session, gym_id)
    db_session.commit()
    role = db_session.scalar(
        select(Role).where(Role.merchant_id == gym_id, Role.code == "gym_admin")
    )
    before = set(
        db_session.scalars(
            select(RolePermission.permission_code).where(RolePermission.role_id == role.id)
        ).all()
    )
    # 人为删掉一个权限点后再次 ensure，不应被模板补回
    row = db_session.scalar(
        select(RolePermission).where(
            RolePermission.role_id == role.id,
            RolePermission.permission_code == "report:read",
        )
    )
    if row:
        db_session.delete(row)
        db_session.commit()
    ensure_merchant_role_packs(db_session, gym_id)
    db_session.commit()
    after = set(
        db_session.scalars(
            select(RolePermission.permission_code).where(RolePermission.role_id == role.id)
        ).all()
    )
    assert "report:read" not in after or "report:read" not in before
    # 若原本有 report:read 且被删，after 仍应无
    if "report:read" in before:
        assert "report:read" not in after
```

- [x] **Step 2: 实现 `role_packs.py`**

```python
"""业态角色模板 → 商户角色实例（A+B）。"""

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
    """按商户已挂子系统复制缺失的角色实例；已存在则跳过（不覆盖 grants）。"""
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
            tpl = db.scalar(
                select(Role).where(Role.merchant_id.is_(None), Role.code == tpl_code)
            )
            if tpl is None:
                continue
            inst = Role(
                code=inst_code,
                name=tpl.name,
                permissions=list(tpl.permissions or []),
                is_site_scope=False,
                merchant_id=merchant_id,
                is_system=False,
            )
            db.add(inst)
            db.flush()
            for p in db.scalars(
                select(RolePermission.permission_code).where(RolePermission.role_id == tpl.id)
            ).all():
                db.add(RolePermission(role_id=inst.id, permission_code=p))
            for m in db.scalars(
                select(RoleMenu.menu_code).where(RoleMenu.role_id == tpl.id)
            ).all():
                db.add(RoleMenu(role_id=inst.id, menu_code=m))
            db.flush()
            result_ids.append(inst.id)
    return result_ids
```

- [x] **Step 3: 在 `replace_merchant_subsystems` 末尾调用**

```python
# subsystems.py 末尾 return codes 前：
from app.systems.platform.services.role_packs import ensure_merchant_role_packs
ensure_merchant_role_packs(db, merchant_id)
return codes
```

注意避免循环 import：若有环，改为在 `org.py` 的 put subsystems 与 seed 显式调用，`replace_merchant_subsystems` 保持纯净。**推荐**：`replace_merchant_subsystems` 不调用；在 `org.py` 两处挂接成功后 + `seed.py`/`seed_demo.py` 显式调用（更清晰）。

- [x] **Step 4: 跑测试**

Run: `docker compose exec backend pytest tests/test_role_packs.py -q`  
Expected: PASS（需先有 Task 2 的 tpl 种子；可先 skip 或 Task 1+2 同批）

- [x] **Step 5: Commit（仅当用户要求）**

---

### Task 2: 重写 `ROLE_DEFS` 与 seed 流程

**Files:**
- Modify: `backend/app/seed.py`（整表替换 `ROLE_DEFS`；seed 后 `ensure_merchant_role_packs`）
- Modify: `backend/app/seed_demo.py`（账号与绑角）

**Interfaces:**
- Produces 场地级角色: `site_admin`, `site_ops`, `tpl_gym_admin`, `tpl_gym_ops`, `tpl_gym_coach`, `tpl_bar_admin`, `tpl_bar_ops`, `tpl_bar_cashier`
- 废弃不再写入: `merchant_admin`, `front_desk`, `coach`, `platform_admin`, 场地级 `gym_admin`/`bar_admin`

- [x] **Step 1: 替换 `ROLE_DEFS` 权限列表（与 spec §3 一致）**

```python
ROLE_DEFS = [
    {"code": "site_admin", "name": "场地管理员", "is_site_scope": True, "permissions": ["*"]},
    {
        "code": "site_ops",
        "name": "场地运营人员",
        "is_site_scope": True,
        "permissions": [
            "system:platform",
            "org:read",
            "member:read", "member:write",
            "access:read", "access:manage",
            "order:read", "order:write",
            "report:read",
        ],
    },
    {
        "code": "tpl_gym_admin",
        "name": "健身房管理员",
        "is_site_scope": False,
        "permissions": [
            "system:platform", "system:gym",
            "org:read", "staff:manage", "rbac:manage",
            "member:read", "member:write",
            "access:read", "access:manage",
            "order:read", "order:write",
            "membership:manage", "membership:sell",
            "coach:manage", "course:manage", "course:book", "course:checkin", "pt:sell",
            "retail:manage", "retail:sell", "retail:read",
            "coupon:manage", "coupon:redeem", "coupon:read",
            "report:read",
            "equipment:manage", "equipment:repair", "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_ops",
        "name": "健身房运营人员",
        "is_site_scope": False,
        "permissions": [
            "system:platform", "system:gym",
            "member:read", "member:write",
            "access:read", "access:manage",
            "order:read", "order:write",
            "membership:sell",
            "course:book", "course:checkin", "pt:sell",
            "retail:sell", "retail:read",
            "coupon:redeem", "coupon:read",
            "equipment:repair", "equipment:read",
        ],
    },
    {
        "code": "tpl_gym_coach",
        "name": "健身房教练",
        "is_site_scope": False,
        "permissions": [
            "system:gym", "member:read", "course:checkin",
            "equipment:read", "equipment:repair",
        ],
    },
    {
        "code": "tpl_bar_admin",
        "name": "清吧管理人员",
        "is_site_scope": False,
        "permissions": [
            "system:platform", "system:catering",
            "org:read", "staff:manage", "rbac:manage",
            "member:read", "member:write",
            "access:read", "access:manage",
            "order:read", "order:write",
            "report:read",
            "catering:menu", "catering:order",
        ],
    },
    {
        "code": "tpl_bar_ops",
        "name": "清吧运营人员",
        "is_site_scope": False,
        "permissions": [
            "system:catering",
            "member:read",
            "order:read", "order:write",
            "catering:menu", "catering:order",
        ],
    },
    {
        "code": "tpl_bar_cashier",
        "name": "清吧收银人员",
        "is_site_scope": False,
        "permissions": [
            "system:catering",
            "member:read",
            "order:read", "order:write",
            "catering:order",
        ],
    },
]
```

- [x] **Step 2: seed 在 `replace_merchant_subsystems` / 找到 gym、bar 后调用 `ensure_merchant_role_packs`；`sync_manifests` 已为模板装菜单**

- [x] **Step 3: `seed_demo` 账号**

| username | merchant | 绑角色实例 |
|----------|----------|------------|
| `site_ops` | null | `site_ops` |
| `gym_admin` | gym | `gym_admin`（merchant 实例） |
| `gym_ops` | gym | `gym_ops` |
| `coach01` / `coach02` | gym | `gym_coach` |
| `bar_admin` | bar | `bar_admin` |
| `bar_ops` | bar | `bar_ops` |
| `bar_cashier` | bar | `bar_cashier` |

用 `_ensure_staff_role` 纠正历史绑角。查找商户实例：

```python
def _merchant_role(db, merchant_id: int, code: str) -> Role:
    return db.scalar(select(Role).where(Role.merchant_id == merchant_id, Role.code == code))
```

`role_map` 仍含场地级/模板；绑员工时用 `_merchant_role`，不要用 `role_map["tpl_gym_admin"]`。

- [x] **Step 4: `org.py` 挂接子系统成功后调用 `ensure_merchant_role_packs(db, row.id)`**

- [x] **Step 5: Docker 重启 seed 日志含完成；手验库内商户角色**

---

### Task 3: assignable / 绑角 / 教练身份

**Files:**
- Modify: `backend/app/systems/platform/api/rbac.py`（`list_assignable_roles`）
- Modify: `backend/app/systems/platform/api/staff.py`（拒绝 `tpl_*`）
- Modify: `backend/app/core/deps.py`（`ROLE_COACH = "gym_coach"`，保留兼容可读旧 `"coach"`）
- Modify: `backend/app/systems/gym/api/course.py`（教练判断）

- [x] **Step 1: assignable 过滤**

```python
# list_assignable_roles 返回前：
rows = [r for r in rows if not r.code.startswith("tpl_")]
```

商户管理员查询：仅 `Role.merchant_id == ctx.merchant_id`（不要回落场地非 site 模板当可选项）。超管指定 `merchant_id` 时：该商户实例 + 场地 `site_ops`（可选）；永不返回 `tpl_*`。

- [x] **Step 2: `_resolve_roles` 拒绝模板**

```python
if code.startswith("tpl_"):
    raise AppError("invalid_role", "不可直接分配角色模板", status_code=400)
```

- [x] **Step 3: 教练身份**

```python
# deps.py
ROLE_COACH = "gym_coach"
ROLE_COACH_LEGACY = "coach"

# course.py 判断
def _is_coach_only(ctx):
    codes = ctx.role_codes
    return (("gym_coach" in codes or "coach" in codes)
            and not ctx.is_site_admin
            and "course:manage" not in ctx.permissions)
```

- [x] **Step 4: 更新测试中的 `role_codes`**

- `test_org_identity.py`: `merchant_admin` → 先 ensure packs 再用 `gym_admin`；`front_desk` → `gym_ops`
- `test_course_ops.py` / `test_reports.py` / `test_member_h5.py`: `"coach"` → `"gym_coach"`（创建员工时 merchant 已有实例）

注意：测试里 `POST /staff` 的 `role_codes: ["gym_coach"]` 依赖该商户已有实例——conftest/seed 须已 `ensure_merchant_role_packs`。

- [x] **Step 5: 跑** `pytest tests/test_role_packs.py tests/test_org_identity.py tests/test_rbac_config.py -q`

---

### Task 4: 登录页与文档

**Files:**
- Modify: `frontend/src/core/views/LoginView.vue`
- Modify: `user.md`, `README.md`
- Modify: `docs/superpowers/specs/2026-08-04-merchant-role-packs-design.md` 状态 → 已落地

- [x] **Step 1: 登录芯片**

```ts
const DEMO_ACCOUNTS = [
  { label: '场地管理员', username: 'admin', password: 'Admin@123456' },
  { label: '场地运营', username: 'site_ops', password: 'Demo@123456' },
  { label: '健身房管理员', username: 'gym_admin', password: 'Demo@123456' },
  { label: '健身房运营', username: 'gym_ops', password: 'Demo@123456' },
  { label: '健身房教练', username: 'coach01', password: 'Demo@123456' },
  { label: '清吧管理员', username: 'bar_admin', password: 'Demo@123456' },
  { label: '清吧运营', username: 'bar_ops', password: 'Demo@123456' },
  { label: '清吧收银', username: 'bar_cashier', password: 'Demo@123456' },
] as const
```

- [x] **Step 2: 更新 `user.md` 表格与可见子系统说明**

- [x] **Step 3: `docker compose up --build -d`；逐个账号登录检查导航**

Expected:
- `site_ops` → 仅 platform
- `gym_admin` → platform + gym
- `coach01` → gym（工作台+器材）
- `bar_cashier` → catering（点单）

---

## Spec coverage

| Spec 项 | Task |
|---------|------|
| A+B 复制算法 | 1 |
| ROLE_DEFS / 废弃旧角色 | 2 |
| 演示账号 | 2、4 |
| 挂接钩子 | 1、2 |
| assignable 排除模板 | 3 |
| 登录文案 | 4 |
| 测试幂等/导航 | 1、3、4 |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-04-merchant-role-packs.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每任务新开子代理，任务间评审  
2. **Inline Execution** — 本会话按 executing-plans 连续执行  

Which approach?
