# 场地/商户角色包（A+B）— 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-04 |
| 状态 | 已落地 |
| 关联 | `2026-08-04-subsystem-rbac-config-design.md`（已有 merchant 角色与配置台）；PRD `2026-08-02-gym-prd-modules-design.md` |
| 范围 | 角色分层、业态模板、开户复制、种子演示账号与登录切换；管理端 Web + 后端 |
| 非目标 | 会员 H5；微前端；手造未注册权限码 |

## 1. 背景与目标

当前演示与登录「快速切换身份」按**子系统**命名（综合经营 / 健身 / 餐饮），与真实组织不符。正确模型是：

1. **场地级**人员管公共能力与框架；
2. **商户级**人员归属具体健身房/清吧等商户；
3. 每个商户有自己的管理员、运营、教练/收银等，并可在本商户已挂子系统范围内配置角色与员工。

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 角色落库策略 | **A+B**：场地维护业态角色**模板**；新建商户时**复制**为该商户角色实例 |
| 命名视角 | 按组织角色（场地管理员、健身房教练…），不按子系统入口 |
| 模板变更影响 | 只影响**之后新开**商户；已复制实例不回溯覆盖 |
| 商户自治 | 商户管理员仅 CRUD `merchant_id=本商户` 的角色实例与绑员工 |

### 1.2 成功标准

- 种子角色清单符合场地 + 健身房包 + 清吧包；登录快速切换按组织角色展示。
- 新建商户（挂 `gym` / `catering`）自动生成对应角色实例（幂等）。
- 演示账号可分别验证：场地管理员/运营、健身房三类、清吧三类。
- 商户管理员可在配置台看到并微调**本商户实例**；超管可维护场地角色与模板。
- 旧笼统角色（`merchant_admin` / `front_desk` / `platform_admin` / 场地级 `gym_admin` 等）迁移或停用，不留歧义绑角。

## 2. 模型：模板与实例

```
场地级 Role (merchant_id IS NULL)
├── site_admin / site_ops          ← 直接授予场地员工
└── tpl_*                          ← 业态标准包，一般不长期绑员工
         │ 开户复制（按 merchant_subsystems）
         ▼
商户级 Role (merchant_id = N)
└── gym_admin / gym_ops / gym_coach
    bar_admin / bar_ops / bar_cashier
```

### 2.1 复制规则

触发时机：

1. `POST/PUT` 商户子系统挂接成功后；
2. Demo/seed 对已有商户幂等补齐。

算法（幂等）：

1. 读取商户已挂 `subsystem_codes`。
2. 若含 `gym`：确保存在 `merchant_id=该商户` 且 `code ∈ {gym_admin, gym_ops, gym_coach}`；缺失则从 `tpl_gym_*` 复制 `name/permissions/role_permissions/role_menus/is_site_scope=false`。
3. 若含 `catering`：同上，复制 `bar_admin/bar_ops/bar_cashier` ← `tpl_bar_*`。
4. 已存在的实例：**不覆盖**权限与菜单（尊重商户已微调）。
5. 商户卸挂某业态：本切片**不自动删角色**（避免误伤）；配置台勾选范围仍受挂接约束。

模板 → 实例 code 映射：`tpl_gym_admin` → `gym_admin`（去掉 `tpl_` 前缀）。

### 2.2 员工绑角

- 场地员工（`staff.merchant_id` 空）：仅绑场地级角色（`site_admin` / `site_ops`）；禁止绑 `tpl_*`（或绑了也无业务价值，assignable 不展示模板）。
- 商户员工：优先绑**本商户实例**；`GET /rbac/roles/assignable` 对本商户管理员返回本商户实例（+ 可选只读展示模板名作参考，不可选）。
- 超管创建员工时可指定商户并选该商户实例。

## 3. 角色与默认权限包

### 3.1 场地级

| code | 名称 | 权限要点 |
|------|------|----------|
| `site_admin` | 场地管理员 | `*` |
| `site_ops` | 场地运营人员 | `system:platform`；`org:read`；`member:read/write`；`access:read/manage`；`order:read/write`；`report:read`；**无** `rbac:manage` / `staff:manage` / 业态写死管理权 |

### 3.2 健身房模板 → 实例

| 模板 code | 实例 code | 名称 | 权限要点 |
|-----------|-----------|------|----------|
| `tpl_gym_admin` | `gym_admin` | 健身房管理员 | `system:platform` + `system:gym`；本商户员工/`rbac:manage`；会员门禁订单；会籍/教练/课程/零售/券/器材全量管理；报表 |
| `tpl_gym_ops` | `gym_ops` | 健身房运营人员 | `system:platform` + `system:gym`；会员写；临访/门禁；办卡售卖；约课核销；零售收银；券核销；器材报修/只读；**无**卡种管理、`rbac:manage`、`coach:manage` 档案大权 |
| `tpl_gym_coach` | `gym_coach` | 健身房教练 | `system:gym`；`member:read`；`course:checkin`；`equipment:read/repair` |

### 3.3 清吧模板 → 实例

| 模板 code | 实例 code | 名称 | 权限要点 |
|-----------|-----------|------|----------|
| `tpl_bar_admin` | `bar_admin` | 清吧管理人员 | `system:platform` + `system:catering`；员工/`rbac:manage`；会员门禁订单；`catering:menu/order`；报表 |
| `tpl_bar_ops` | `bar_ops` | 清吧运营人员 | `system:catering`；`catering:menu` + `catering:order`；必要 `order:read/write`、`member:read` |
| `tpl_bar_cashier` | `bar_cashier` | 清吧收银人员 | `system:catering`；`catering:order`；`order:read/write`；`member:read` |

菜单授予：沿用现有「按权限 + `system:xxx` 门禁」自动装配；模板与实例同步后走 `sync_role_menus` / 复制时带上 `role_menus`。

### 3.4 废弃 / 迁移

| 旧 code | 处理 |
|---------|------|
| `platform_admin` | 能力并入 `site_ops`（或保留别名账号指向 `site_ops` 一版后删除） |
| `merchant_admin` | 不再作为默认绑角；由商户 `gym_admin`/`bar_admin` 实例替代 |
| `front_desk` | 由 `gym_ops` 替代（健身房）；清吧侧不复用 |
| 场地级 `gym_admin` / `bar_admin` / `coach` | 改为 `tpl_*`；员工改绑商户实例 `gym_coach` 等 |

Seed 对已有员工：按用户名纠正绑到对应商户实例角色。

## 4. 配置台与 API

在现有 `/api/v1/rbac/*` 上增量：

| 能力 | 说明 |
|------|------|
| 角色列表 | 超管可见场地角色 + 全部模板 +（可选）各商户实例；商户管理员仅本商户实例 |
| `POST` 商户子系统 | 成功后调用 `ensure_merchant_role_packs(merchant_id)` |
| 模板标记 | `roles` 增加 `is_template`（或约定 `code LIKE 'tpl_%'`）；assignable **排除**模板 |
| 演示账号 | seed_demo 写入下表账号；登录页芯片按组织角色文案 |

不新增独立微服务；复制逻辑放 `core` 或 `systems/platform/services/role_packs.py`。

## 5. 演示账号与登录文案

| 芯片文案 | 账号 | 密码 | 角色 |
|----------|------|------|------|
| 场地管理员 | `admin` | `Admin@123456` | `site_admin` |
| 场地运营 | `site_ops` | `Demo@123456` | `site_ops` |
| 健身房管理员 | `gym_admin` | `Demo@123456` | 健身房商户 `gym_admin` |
| 健身房运营 | `gym_ops` | `Demo@123456` | 健身房商户 `gym_ops` |
| 健身房教练 | `coach01` | `Demo@123456` | 健身房商户 `gym_coach` |
| 清吧管理员 | `bar_admin` | `Demo@123456` | 清吧商户 `bar_admin` |
| 清吧运营 | `bar_ops` | `Demo@123456` | 清吧商户 `bar_ops` |
| 清吧收银 | `bar_cashier` | `Demo@123456` | 清吧商户 `bar_cashier` |

可选兼容：`catering_admin` → 同 `bar_admin`；`platform_admin` → 同 `site_ops`（一版后可删）。

同步更新 `user.md` / README。

## 6. 风险与测试

| 风险 | 对策 |
|------|------|
| 复制覆盖商户已改权限 | 仅「不存在则创建」，不覆盖已有实例 |
| 员工仍绑旧场地级角色 | seed 纠正 + assignable 隐藏模板与废弃 code |
| 菜单空白 | 复制时同步 `role_menus`；启动 `sync_manifests` 对模板重算 |
| 测试依赖旧 role code | 更新 `test_rbac_config` / staff 创建用例中的 `role_codes` |

测试要点：

1. 创建仅挂 gym 的商户 → 仅 3 个 gym 实例；挂 catering → 3 个 bar 实例。
2. 二次挂接幂等，不改已有实例权限。
3. `coach01` 导航仅健身工作台+器材；`bar_cashier` 仅餐饮点单相关。
4. 登录芯片文案与账号表一致。

## 7. 实施顺序（实现计划细化）

1. 数据：`is_template`（可选）+ `ensure_merchant_role_packs`。
2. 重写 `ROLE_DEFS` 为场地 + `tpl_*`；删除/停用旧 code。
3. 商户子系统写入钩子调用复制。
4. seed_demo 账号与绑角；登录页与文档。
5. 配置台/assignable 过滤模板。
6. 回归测试与 Docker 冒烟。
