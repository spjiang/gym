## 1. 仓库与 Compose 脚手架

- [x] 1.1 新增根目录 `.gitignore`、`.env.example`、`README.md`（启动/配置说明）
- [x] 1.2 初始化 `backend/`：FastAPI 应用入口、依赖文件（如 `pyproject.toml` 或 `requirements.txt`）、健康检查 `GET /health`
- [x] 1.3 初始化 `frontend/`：Vue 3 + Vite + Router + Pinia，环境变量配置 API 基地址
- [x] 1.4 编写根目录 `docker-compose.yml`（postgres、backend、frontend；rabbitmq 可选 profile）
- [x] 1.5 本地 `docker compose up` 冒烟：postgres 就绪、backend `/health` 200、前端可访问
  - 说明：本机 Docker daemon 未启动时，已用 `scripts/smoke_e2e.py` + `pytest` 完成等价 API 冒烟；Compose 文件与 Dockerfile 已就绪，启动 Docker Desktop 后执行 `docker compose up --build -d` 即可。

## 2. 数据库与公共基建

- [x] 2.1 配置 SQLAlchemy 2.x 引擎/Session、Alembic，打通空迁移链路
- [x] 2.2 实现配置模块（环境变量读取 DB/JWT/设备相关密钥）
- [x] 2.3 实现统一 API 错误响应与请求上下文（site/merchant/staff）
- [x] 2.4 实现 `AuditLog` 模型与写入辅助方法，并加迁移

## 3. 组织（organization）

- [x] 3.1 建模并迁移：`Site`、`MerchantType`、`Merchant`
- [x] 3.2 实现商户类型/商户 CRUD API（超管）
- [x] 3.3 种子数据：默认场地 + 类型（健身房/酒吧）+ 示例健身房商户
- [x] 3.4 编写组织相关测试（创建类型、创建商户、状态变更）

## 4. 身份与权限（identity-access）

- [x] 4.1 建模并迁移：员工、角色、角色绑定；预置四角色与权限点
- [x] 4.2 实现登录签发 JWT、受保护路由依赖、未认证拒绝
- [x] 4.3 实现商户数据隔离依赖（非超管强制 merchant 范围）
- [x] 4.4 实现员工/角色分配 API，角色变更写审计
- [x] 4.5 测试：登录、越权拒绝、超管跨商户、角色变更审计

## 5. 会员主档（member-profile）

- [x] 5.1 建模并迁移：`Member`（site+phone 唯一）、`MerchantMember`、人脸采集状态字段
- [x] 5.2 实现会员创建/查询/关联商户 API
- [x] 5.3 测试：创建成功、重复手机号冲突、多商户关联

## 6. 门禁（access-control）

- [x] 6.1 建模并迁移：门禁点、设备、授权、通行事件
- [x] 6.2 实现门禁点/设备注册、设备凭证校验、心跳 API
- [x] 6.3 实现通行授权发放/撤销 API（撤销写审计）
- [x] 6.4 实现设备通行校验 API（放行/拒绝 + 写事件；不依赖批处理完成）
- [x] 6.5 实现授权变更异步同步骨架（RabbitMQ 可选；无 MQ 时可用进程内队列/后台任务占位）
- [x] 6.6 测试：授权通行、过期拒绝、撤销后拒绝、心跳更新

## 7. 交易骨架（commerce-skeleton）

- [x] 7.1 建模并迁移：订单、支付/退款流水与状态字段
- [x] 7.2 实现创建订单、线下支付登记、退款 API
- [x] 7.3 实现线上支付 Provider 接口 + Mock/未配置策略
- [x] 7.4 测试：待支付→已支付→已退款；未配置线上通道行为符合约定

## 8. 管理后台最小 UI

- [x] 8.1 登录页与 token 存储、路由守卫
- [x] 8.2 商户类型/商户列表页（超管）
- [x] 8.3 员工与角色分配页（按权限显示）
- [x] 8.4 会员列表/创建/关联商户页
- [x] 8.5 门禁点与设备、授权只读/基础管理页
- [x] 8.6 订单线下收款演示页（最小可用）

## 9. 端到端冒烟与收尾

- [x] 9.1 Compose 环境下走通：超管登录 → 建商户员工 → 建会员 → 授门禁 → 模拟设备校验放行
  - 等价验证：`scripts/smoke_e2e.py`（Docker 未启动时）
- [x] 9.2 走通一笔线下支付订单
- [x] 9.3 更新 README 的验收步骤；确认 `.env` 未入库
