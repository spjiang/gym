# 子系统目录隔离与可配置 RBAC — 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-04 |
| 状态 | 待用户审阅 |
| 关联 | PRD `2026-08-02-gym-prd-modules-design.md`；既有商户业态挂接 `merchant_subsystems` |
| 范围 | 管理端 Web + 后端；**不含**会员 H5 / 小程序目录改造 |

## 1. 背景与目标

场地需长期扩展多种业态子系统（当前：综合经营、健身、餐饮）。要求：

1. **源码按子系统目录隔离**（前后端均拆），便于以后新增子系统而不污染其它目录。
2. **综合经营**是场地/超管子系统，负责组织、子系统装配、RBAC 等配置。
3. **RBAC 与菜单可见性可配置**：权限点与菜单由子系统代码注册；谁拥有哪些权限/看见哪些菜单在库内装配，界面可改，避免写死在种子或前端常量里。

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 目录隔离深度 | 前后端均按 `systems/{platform,gym,catering}` 拆 |
| RBAC 灵活度 | 角色权限 + 菜单可见性可配；能力目录由 manifest 注册 |
| 配置权限 | 超管定框架；商户管理员可本商户微调角色/菜单 |
| 交付节奏 | 本切片同时完成目录迁移 + 配置台 |
| 装配方式 | Manifest 注册 + 库内装配 |
| 会员 H5 | 本切片不动；保证 API 路径兼容 |

### 1.2 成功标准

- 三个子系统源码落在独立目录，子系统间不互相 import 业务实现。
- 超管可启停子系统、维护场地级角色的权限与可见菜单。
- 商户管理员可在本商户创建/编辑角色，勾选范围不超过「已挂业态 ∩ 已启用能力」。
- 登录后侧栏/门户菜单来自 `/me/navigation`，改配置刷新即生效。
- 现有业务 URL 与权限码行为保持兼容；清吧/健身房业态隔离与餐饮闭环仍可用。
- 会员 H5 冒烟通过（无结构改造）。

## 2. 架构与目录

运行时仍是 **一个后端进程 + 一个管理端 SPA**（Docker Compose 不变）。隔离在源码与注册边界，而非独立部署。

```
backend/app/
├── core/                         # db、auth、errors、中间件、manifest 同步
├── systems/
│   ├── platform/                 # 综合经营
│   │   ├── manifest.py
│   │   ├── api/
│   │   ├── models/               # 以迁入为主；共享模型可暂留 core 或逐步迁
│   │   └── services/
│   ├── gym/
│   │   ├── manifest.py
│   │   ├── api/
│   │   └── …
│   └── catering/
│       ├── manifest.py
│       └── …
└── main.py                       # 发现系统、挂载 router、sync_manifests()

frontend/src/
├── core/                         # http、auth、Layout、Portal 壳
├── systems/
│   ├── platform/
│   │   ├── manifest.ts           # path → 组件注册（非菜单权威源）
│   │   ├── routes.ts
│   │   └── views/
│   ├── gym/
│   │   ├── manifest.ts
│   │   ├── routes.ts
│   │   └── views/
│   └── catering/
│       ├── …
└── router/index.ts               # 聚合 routes；守卫结合 navigation
```

### 2.1 约定

- 子系统 `code`：`platform` | `gym` | `catering`（新增子系统 = 新目录 + manifest）。
- `platform` **不是**商户业态；商户仅挂 `gym` / `catering` 等 `is_business=true` 的子系统。
- 子系统之间禁止互相 import 业务实现；共享契约放 `core/`。
- 对外 HTTP 路径尽量保持现网不变（如 `/api/v1/membership-products`、前端 `/products`）。

## 3. 数据模型

### 3.1 能力目录（代码同步，配置台不手造码）

| 表 | 字段要点 |
|----|----------|
| `subsystems` | `code` PK、`name`、`description`、`is_business`、`sort_order`、`is_enabled`、`is_deprecated` |
| `permission_defs` | `code` 唯一、`subsystem_code`、`name`、`is_deprecated` |
| `menu_defs` | `code` 唯一、`subsystem_code`、`path`、`name`、`required_any`（JSON 权限码列表）、`sort_order`、`is_deprecated` |

启动时 `sync_manifests()` 对上述表 **upsert**；代码中消失的项标记 `is_deprecated`，不物理删除，避免角色引用断裂。

### 3.2 装配（配置台可写）

| 表 | 字段要点 |
|----|----------|
| `roles`（扩展） | 现有 `name/is_site_scope`；新增 `merchant_id`（空=场地级；有值=商户角色）、`is_system`；`code` 唯一约束改为 **`(merchant_id, code)`**（场地级用 `merchant_id IS NULL` 语义，实现可用部分唯一索引或 `coalesce`）；`permissions` JSON 列作迁移兼容，读写以规范表为准 |
| `role_permissions` | `role_id` + `permission_code` |
| `role_menus` | `role_id` + `menu_code` |
| `merchant_subsystems` | 已有，商户挂接业态 |

### 3.3 授权规则

1. **超管**：启停子系统；维护场地级角色；查看完整权限/菜单目录。
2. **商户管理员**：仅 CRUD `merchant_id=本商户` 的角色；可勾权限/菜单 ⊆（场地启用目录 ∩ 本商户已挂子系统）。
3. **员工绑角色**：超管可绑场地级或任意商户角色；商户管理员只能绑本商户角色。
4. **登录聚合**：`permissions = ⋃ 角色权限`；菜单 = `⋃ 角色菜单`，再过滤子系统启停与（业态系统）商户挂接。
5. **`*`**：仅场地超管系统角色；商户角色禁止授予 `*`。

### 3.4 种子迁移

将现有 `ROLE_DEFS` 与前端菜单声明写入各系统 manifest；首次同步后把角色 JSON 权限展开为 `role_permissions`，并按现网菜单生成 `role_menus`，保证迁移后默认可见性与现网一致。

## 4. 配置台与 API

配置台页面均属 **platform** 子系统。

### 4.1 页面

| 路由 | 使用者 | 能力 |
|------|--------|------|
| `/platform/subsystems` | 超管 | 子系统启停、排序；只读权限点/菜单目录 |
| `/platform/roles` | 超管 | 场地级角色 CRUD；按子系统分组勾选权限与菜单 |
| 同页或商户范围列表 | 商户管理员 | 本商户角色 CRUD（范围受限） |
| `/merchants` | 超管 | 继续维护 `merchant_subsystems` |
| `/staff` | 超管/商户管理员 | 角色选项改为 `GET /roles/assignable`，去掉前端写死角色列表 |

侧栏与门户入口以 **`GET /me/navigation`** 为准；各系统 `manifest.ts` 只负责 path→组件映射。

### 4.2 API

配置类接口统一挂在 **`/api/v1/rbac/*`**（避免与现有业态目录 `GET /subsystems` 等冲突）。员工导航可用 `/api/v1/me/navigation`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/rbac/subsystems` | 列表 |
| PATCH | `/rbac/subsystems/{code}` | 启停/排序（超管） |
| GET | `/rbac/permission-defs` | 可按 subsystem 过滤 |
| GET | `/rbac/menu-defs` | 同上 |
| GET/POST/PATCH/DELETE | `/rbac/roles` | 角色；商户管理员强制本商户 |
| PUT | `/rbac/roles/{id}/grants` | `permission_codes` + `menu_codes` |
| GET | `/rbac/roles/assignable` | 员工绑定候选 |
| GET | `/me/navigation` | `{ subsystems[], menus[] }` 已裁剪 |

写操作记审计；越权 403。

> 既有 `GET /merchants/{id}/order-types`、`PUT /merchants/{id}/subsystems`（商户挂业态）保留，不迁入 rbac 前缀。

## 5. 迁移、风险与测试

### 5.1 实施顺序

1. 建表与同步器；扩展 `roles`。
2. 编写三份后端 manifest；启动同步；迁移现有角色 grants。
3. 后端 API 迁入 `systems/*`；`main` 聚合；对外路径不变。
4. 鉴权读 `role_permissions`（短暂兼容旧 JSON）。
5. 前端迁目录；导航改读库；落地配置台；改造员工绑角色。
6. 全量回归（见下）。

### 5.2 风险与对策

| 风险 | 对策 |
|------|------|
| 搬迁漏路由 | 路径保持不变；构建与冒烟必过 |
| 角色菜单漏配导致空白侧栏 | 种子按现网全量授予；超管 `*` 可见全部启用菜单 |
| 商户越权勾选 | grants API 服务端强制 ⊆ 校验 |
| JSON 与规范表双写不一致 | 统一读 grants；写只更新 grants（可选回写 JSON 过渡） |

### 5.3 测试清单

- 单元：manifest 同步幂等；grants 越权 403；navigation 裁剪。
- API：启停子系统；商户角色微调；assignable 角色范围。
- 手工：`admin` / `gym_admin` / `bar_admin` 门户与侧栏差异；餐饮收款退款；健身房办卡；H5 冒烟。

### 5.4 非目标（本切片不做）

- 会员 H5 / 小程序按子系统拆目录。
- 微前端或多后端独立部署。
- 在数据库中手造未在 manifest 注册的权限码或页面路由。

## 6. 验收对照（产品级）

- [ ] 源码目录三分：platform / gym / catering（前后端）。
- [ ] 超管关闭 `gym` 后，管理端不再出现健身菜单入口。
- [ ] `bar_admin` 无法为清吧角色勾选会籍类权限/菜单。
- [ ] 修改角色菜单后刷新即可，无需发版。
- [ ] 既有业态订单类型隔离与餐饮闭环仍通过。
- [ ] 会员 H5 关键路径可用（未改结构）。
