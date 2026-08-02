## Context

仓库为空工程骨架阶段，产品范围见 `proposal.md` 与 PRD 第 4 章。行为契约见本 change 下 `specs/*`。需在一次 change 内同时定下目录、运行时与底座模块边界，避免后续业态包推倒重来。

## Goals / Non-Goals

**Goals:**

- 选定可落地的 Python Web / Vue 技术选型与仓库布局
- 定义核心表与 API 边界，使组织、鉴权、会员、门禁、订单骨架可联调
- Compose 一键起依赖；门禁校验与异步同步路径分离

**Non-Goals:**

- 不选定具体人脸 Pad 品牌 SDK 的完整对接细节（保留设备凭证、心跳、校验、同步任务接口即可）
- 不定稿小程序端完整信息架构
- 不引入微服务拆分；一期单体后端 + 独立前端

## Decisions

### 1. 后端框架：FastAPI + SQLAlchemy 2.x + Alembic

- **选择**：FastAPI（异步友好、OpenAPI 自带）、SQLAlchemy 2.0 风格、Alembic 迁移
- **理由**：与「禁止过时 API」、类型提示与快速出 OpenAPI 一致；迁移可重复
- **备选**：Django/DRF（更重、一期收益不高）

### 2. 前端：Vue 3 + Vite + Vue Router + Pinia

- **选择**：管理后台 SPA；API 基地址环境变量配置
- **理由**：符合项目 Rules；Composition API 为默认
- **备选**：Nuxt（本期无 SSR 强需求）

### 3. 鉴权：员工 JWT（访问令牌）+ 设备 API Key/设备令牌

- **选择**：人与设备凭证分离；RBAC 权限点校验；请求上下文带 `site_id` / `merchant_id`
- **理由**：满足门禁设备与员工登录分离；超管与商户隔离对齐 specs
- **备选**：Session Cookie（Pad 与多端不如 Bearer 清晰）

### 4. 数据模型（逻辑实体）

- `Site` 场地
- `MerchantType` / `Merchant`（type、status）
- `StaffUser`、`Role`、`StaffRole`、权限点集合
- `Member`（site 唯一 phone）、`MerchantMember` 关联
- `AccessPoint`、`AccessDevice`、`AccessGrant`、`AccessEvent`
- `Order`、`Payment`、`Refund`（或支付流水统一表）
- `AuditLog`

商户隔离：除超管外，查询默认强制 `merchant_id` 条件。

### 5. Compose 拓扑

- 服务：`postgres`、`backend`、`frontend`（开发可用 Vite，Compose 可用 nginx 托管构建产物或 dev 服务）
- `rabbitmq`：profile 或环境开关启用；用于授权变更同步、通知预留
- 应用通过服务名连接 `postgres` / `rabbitmq`

### 6. 门禁路径

- **同步路径**：`POST /device/access/verify`（名称可微调）只读授权表 → 写事件 → 返回放行/拒绝；不做批量下发等待
- **异步路径**：授权变更发布消息 → worker 生成设备同步任务；失败可重试，不影响校验以服务端为准

### 7. 支付骨架

- 统一订单状态机：待支付 → 已支付 → 已退款（可加取消）
- `OfflinePaymentRegistrar` + `OnlinePaymentProvider` 接口；默认 `Noop`/`Mock` 实现
- 真实微信通道留给后续 change

### 8. API 前缀与模块包

- 后端包按领域分：`org`、`identity`、`members`、`access`、`commerce`、`audit`
- REST 前缀建议 `/api/v1/...`；设备接口 `/api/v1/device/...`

## Risks / Trade-offs

- [Pad 品牌未知] → 先抽象设备协议与同步任务；厂家对接作为后续 change  
- [单体后期膨胀] → 按领域包边界拆分，表与 API 已按商户隔离，便于再拆  
- [异步与校验短暂不一致] → 校验以服务端授权为准；设备本地缓存策略后续再定（PRD 已允许实现计划选定）  
- [首 change 范围仍偏大] → tasks 按垂直切片排序，先 Compose+健康检查，再组织/鉴权，再会员/门禁/订单

## Migration Plan

- 全新库：Alembic 初始迁移一次建齐底座表；种子数据写入超管、默认场地、示例商户类型  
- 回滚：开发期可重建卷；无生产迁移负担  
- 配置：复制 `.env.example` → `.env` 后 `docker compose up`

## Open Questions

- 人脸特征值存储位置（仅设备侧 vs 服务端密文）：不阻塞本 change 表结构，会员仅保留采集状态枚举  
- 前端 UI 组件库选型（如 Element Plus）：实现 tasks 时选定即可，不影响 specs  
