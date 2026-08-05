# 子系统目录隔离与可配置 RBAC Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 前后端按 `systems/{platform,gym,catering}` 隔离源码；子系统 manifest 同步入库；综合经营提供子系统启停与角色权限/菜单配置台；登录导航改为读库裁剪；业务 URL 与 H5 兼容不变。

**Architecture:** 各子系统目录内 `manifest` 声明权限点与菜单；启动 `sync_manifests()` upsert 到 `subsystems` / `permission_defs` / `menu_defs`；角色装配用 `role_permissions` / `role_menus`（支持场地级与商户级角色）；管理端配置台走 `/api/v1/rbac/*`，壳层拉 `/me/navigation`。

**Tech Stack:** FastAPI · SQLAlchemy 2 · Alembic · pytest · Vue 3 · Pinia · Element Plus · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-04-subsystem-rbac-config-design.md`

## Global Constraints

- 交流与代码注释使用中文；禁止过时 API
- 对外 `/api/v1/...` 与管理端业务 path 尽量不变；会员 H5 **不改结构**
- 子系统间禁止互相 import 业务实现；共享仅 `core/`
- `platform` 非商户业态；商户只挂 `is_business` 子系统
- 商户角色 grants ⊆ 已启用目录 ∩ 本商户已挂业态；禁止商户角色授予 `*`
- 产品级闭环：配置台按钮可用、越权 403、导航刷新生效
- 未要求时不 git commit；完成后回写 PRD §10
- 验证：`pytest` + `docker compose build/up` 冒烟

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/core/` | 从现有 `db/deps/errors/security/config` 迁入或薄封装；`manifest_sync.py` |
| `backend/app/models/rbac_catalog.py` | `Subsystem` / `PermissionDef` / `MenuDef` / `RolePermission` / `RoleMenu` |
| `backend/app/models/identity.py` | `Role` 增加 `merchant_id`、`is_system`；调整 code 唯一 |
| `backend/alembic/versions/20260804_0011_rbac_catalog.py` | 建表与角色列迁移、回填 grants |
| `backend/app/systems/platform/manifest.py` | platform 权限+菜单 |
| `backend/app/systems/gym/manifest.py` | gym |
| `backend/app/systems/catering/manifest.py` | catering |
| `backend/app/systems/*/api/` | 从 `app/api/*` 迁入对应模块 |
| `backend/app/systems/platform/api/rbac.py` | `/rbac/*` 配置 API |
| `backend/app/systems/platform/api/navigation.py` | `/me/navigation` |
| `backend/app/main.py` | 发现系统、挂载、sync |
| `backend/app/deps.py` 或 `core/authz.py` | 权限读取改走 `role_permissions`（兼容 JSON） |
| `backend/app/seed.py` | 系统角色 `is_system`；减少硬编码权限合并逻辑依赖 grants |
| `backend/tests/test_rbac_config.py` | 同步/grants/navigation/越权 |
| `frontend/src/core/` | http、auth、Layout、Portal |
| `frontend/src/systems/{platform,gym,catering}/` | views、routes、manifest（组件注册） |
| `frontend/src/systems/platform/views/SubsystemsView.vue` | 子系统配置 |
| `frontend/src/systems/platform/views/RolesView.vue` | 角色权限/菜单 |
| `frontend/src/router/index.ts` | 聚合 routes |
| `frontend/src/views/StaffView.vue`（迁后路径） | assignable 角色 |
| PRD §10 | 进度回写 |

---

### Task 1: RBAC 目录模型与迁移

**Files:**
- Create: `backend/app/models/rbac_catalog.py`
- Modify: `backend/app/models/identity.py`
- Modify: `backend/app/models/__init__.py`
- Create: `backend/alembic/versions/20260804_0011_rbac_catalog.py`（`down_revision` 接当前 head）

**Interfaces:**
- Produces: 表 `subsystems`, `permission_defs`, `menu_defs`, `role_permissions`, `role_menus`；`roles.merchant_id`、`roles.is_system`
- Produces 模型: `Subsystem`, `PermissionDef`, `MenuDef`, `RolePermission`, `RoleMenu`

- [ ] **Step 1: 写失败测试（表/模型可导入并建表）**

```python
# backend/tests/test_rbac_config.py
def test_rbac_models_importable():
    from app.models.rbac_catalog import Subsystem, PermissionDef, MenuDef, RolePermission, RoleMenu
    assert Subsystem.__tablename__ == "subsystems"
```

- [ ] **Step 2: 实现模型与 Alembic；`roles` 唯一约束改为支持 `(merchant_id, code)`（SQLite/Postgres 兼容方案写在迁移注释）**

- [ ] **Step 3: 迁移内 data migration：为已有角色插入 `role_permissions`（从 JSON `permissions` 展开）；`site_admin.is_system=True`**

- [ ] **Step 4: 跑测试**

Run: `cd backend && pytest tests/test_rbac_config.py::test_rbac_models_importable -q`  
Expected: PASS（或在 Docker 内挂载 tests 跑）

---

### Task 2: Manifest 定义与 sync_manifests

**Files:**
- Create: `backend/app/core/manifest_sync.py`
- Create: `backend/app/systems/platform/manifest.py`
- Create: `backend/app/systems/gym/manifest.py`
- Create: `backend/app/systems/catering/manifest.py`
- Create: `backend/app/systems/__init__.py`（`iter_system_manifests()`）
- Modify: `backend/app/main.py` 或 `scripts/entrypoint` 启动路径调用 sync
- Modify: `backend/tests/test_rbac_config.py`

**Interfaces:**
- Produces:

```python
# 每个 manifest 导出
SYSTEM = {
  "code": "gym",
  "name": "健身管理平台",
  "is_business": True,
  "sort_order": 20,
  "permissions": [{"code": "membership:sell", "name": "会籍售卖"}, ...],
  "menus": [{"code": "gym.products", "path": "/products", "name": "会籍卡种",
             "required_any": ["membership:manage", "membership:sell", "*"], "sort_order": 10}, ...],
}

def sync_manifests(db: Session) -> None: ...
```

- [ ] **Step 1: 失败测试 — sync 后 DB 含 platform/gym/catering 与关键权限/菜单**

```python
def test_sync_manifests_upsert(client, admin_headers):
    # client fixture 已 seed；再调 sync 或依赖启动
    r = client.get("/api/v1/rbac/subsystems", headers=admin_headers)
    # 本步若 API 未就绪，改为直接 Session 调 sync_manifests 断言
    ...
```

本 Task 可先测纯函数：打开 Session 调 `sync_manifests`，断言三行 subsystem。

- [ ] **Step 2: 从现网 `seed.ROLE_DEFS` + `frontend/src/nav/systems.ts` 抄齐权限与菜单到三份 manifest（含配置台新菜单占位：`/platform/subsystems`、`/platform/roles`）**

- [ ] **Step 3: 实现幂等 upsert；缺失项 `is_deprecated=True`**

- [ ] **Step 4: 首次 sync 后为系统角色补全 `role_menus`（按角色 permissions 匹配 `required_any`）**

- [ ] **Step 5: pytest 通过**

---

### Task 3: `/rbac/*` 与 `/me/navigation` API

**Files:**
- Create: `backend/app/systems/platform/api/rbac.py`
- Create: `backend/app/systems/platform/api/navigation.py`
- Modify: `backend/app/main.py` include routers
- Modify: `backend/app/deps.py`（或新建 `core/authz.py`）聚合权限优先 `role_permissions`
- Modify: `backend/tests/test_rbac_config.py`

**Interfaces:**
- Produces endpoints（均前缀 `/api/v1`）:
  - `GET/PATCH /rbac/subsystems`
  - `GET /rbac/permission-defs`、`GET /rbac/menu-defs`
  - `CRUD /rbac/roles`、`PUT /rbac/roles/{id}/grants`、`GET /rbac/roles/assignable`
  - `GET /me/navigation` → `{ subsystems: [...], menus: [...] }`
- Grants 校验：商户角色不可含 `*`；permission/menu 的 subsystem 必须启用且（业态则）商户已挂接

- [ ] **Step 1: 失败测试**

```python
def test_bar_admin_cannot_grant_membership_perm(client, admin_headers):
    # 建清吧商户角色，PUT grants 含 membership:sell → 403
    ...

def test_disable_gym_hides_from_navigation(client, admin_headers):
    client.patch("/api/v1/rbac/subsystems/gym", headers=admin_headers, json={"is_enabled": False})
    nav = client.get("/api/v1/me/navigation", headers=admin_headers).json()
    assert all(m["subsystem_code"] != "gym" for m in nav["menus"])
```

- [ ] **Step 2: 实现 API + 越权校验 + 审计**

- [ ] **Step 3: `require_permission` 读 grants（无 grants 行时回退 Role.permissions JSON）**

- [ ] **Step 4: pytest 全绿**

---

### Task 4: 后端按 systems 目录迁 API

**Files:**
- Move: `backend/app/api/org.py` 等 → `systems/platform/api/`
- Move: membership/course/retail/coupons/equipment → `systems/gym/api/`
- Move: catering → `systems/catering/api/`
- Keep: `device.py` 等跨端接口放 `platform` 或 `core`（门禁设备偏 platform）
- Modify: `main.py` 从 `systems.*.api` 聚合 `include_router`
- Modify: 全仓 import 路径；`tests/` 仍打同一 URL

**Interfaces:**
- Produces: 对外路由表与迁前一致；内部模块路径变更

- [ ] **Step 1: 按清单物理迁移文件并修 import（可用临时 `__init__` re-export 减痛）**

- [ ] **Step 2: 跑既有测试子集**

Run: `pytest tests/test_subsystems_catering.py tests/test_org_identity.py tests/test_members_access_commerce.py -q`  
Expected: PASS

- [ ] **Step 3: 删除或将旧 `app/api/` 变为兼容 re-export 层（二选一，优先薄 re-export 一周内可删）**

---

### Task 5: 前端目录拆分 + navigation 驱动菜单

**Files:**
- Create: `frontend/src/core/`（迁入 `api/http.ts`、`stores/auth.ts`、`LayoutView`、`PortalView`、`LoginView`）
- Create: `frontend/src/systems/platform|gym|catering/{routes.ts,manifest.ts,views/*}`
- Modify: `frontend/src/router/index.ts` 聚合
- Modify: `LayoutView` / `PortalView`：菜单与门户卡片来自 `auth.navigation`（登录/`fetchMe` 后拉 `/me/navigation`）
- Deprecate: `frontend/src/nav/systems.ts` 硬编码菜单（保留类型辅助或删除）

**Interfaces:**
- `auth` store 增加 `navigation: { subsystems, menus }`
- `menusForSystem(systemId)` 改为 filter `navigation.menus`

- [ ] **Step 1: 迁文件修 import，保证 `npm run build` 通过**

- [ ] **Step 2: 接入 `/me/navigation`；无菜单权限时回退 portal**

- [ ] **Step 3: Docker 重建 frontend，手工登录 admin 侧栏仍完整**

---

### Task 6: 配置台 UI + Staff 可分配角色

**Files:**
- Create: `frontend/src/systems/platform/views/SubsystemsView.vue`
- Create: `frontend/src/systems/platform/views/RolesView.vue`
- Modify: Staff 视图：角色多选自 `/rbac/roles/assignable`
- Modify: platform manifest 菜单已在 Task 2 注册；路由挂上

**Interfaces:**
- SubsystemsView: 表格启停开关 → `PATCH /rbac/subsystems/{code}`
- RolesView: 角色列表 + 抽屉内按子系统分组的权限/菜单 checkbox → `PUT .../grants`
- 商户管理员打开 RolesView 仅见本商户角色；创建默认带 `merchant_id`

- [ ] **Step 1: 实现两页，错误用 ElMessage 展示后端 `message`**

- [ ] **Step 2: Staff 去掉写死 `ROLE_OPTIONS`**

- [ ] **Step 3: 手工验收**
  - admin 关闭 gym → 刷新后健身入口消失
  - bar_admin 建角色无法勾会籍权限（前端禁用 + 后端 403）
  - gym_admin 本商户角色微调后侧栏变化

---

### Task 7: 种子/Demo 对齐与全量回归

**Files:**
- Modify: `backend/app/seed.py`、`seed_demo.py`（角色 `is_system`；bar_admin/gym 角色 menus）
- Modify: `user.md` / `README.md`（配置台入口说明）
- Modify: `docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` §10
- Modify: design 文档状态 → 已落地（或实现后改）

- [ ] **Step 1: 重建 backend/frontend，确认迁移+sync+seed**

- [ ] **Step 2: 跑**

```bash
pytest tests/test_rbac_config.py tests/test_subsystems_catering.py -q
# 冒烟：admin / gym_admin / bar_admin 登录导航；餐饮闭环；H5 打开登录页
```

- [ ] **Step 3: 勾选 design §6 验收项；回写 PRD §10（组织/RBAC 行备注子系统配置台）**

---

## Spec Coverage Check

| Spec 要求 | Task |
|-----------|------|
| 前后端 systems 目录三分 | 4、5 |
| Manifest + sync 入库 | 2 |
| 角色权限+菜单可配；超管/商户规则 | 1、3、6 |
| `/rbac/*`、`/me/navigation` | 3、5、6 |
| URL 兼容、H5 不动 | 4、7 |
| 测试与验收 | 3、7 |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-04-subsystem-rbac-config.md`.

**两种执行方式：**

1. **Subagent-Driven（推荐）** — 每 Task 新开子代理，Task 间我做审查  
2. **Inline Execution** — 本会话按 `executing-plans` 连续做，设检查点  

你要哪一种？回复 `1` 或 `2` 即可开始。
