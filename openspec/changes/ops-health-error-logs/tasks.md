## 1. 数据模型与追踪

- [x] 1.1 Alembic：`audit_logs.request_id`、新建 `error_events`
- [x] 1.2 请求级 `request_id` 中间件与 `X-Request-ID`；审计信封带上该字段
- [x] 1.3 `record_error`：独立会话、脱敏、堆栈截断、30 天清理

## 2. 探活与异常

- [x] 2.1 `GET /ready`（Postgres 决定成败，MinIO 仅降级）；`GET /health` 保持存活探查
- [x] 2.2 全局异常：4xx 写入审计详情；5xx/支付系统码/未捕获写入错误事件
- [x] 2.3 支付回调 FAIL 路径主动 `record_error`

## 3. 运维 API 与权限

- [x] 3.1 `devops:read`、菜单「错误日志」「服务状态」；`site_ops` 授予
- [x] 3.2 `GET /api/v1/ops/health-status`、`GET /api/v1/ops/error-events`（筛选含 request_id）
- [x] 3.3 后端测试：探活/探就绪、request_id、校验拒单不进错误表、500 与回调 FAIL 进表、权限

## 4. 管理端与部署

- [x] 4.1 运维管理页：错误日志、服务状态；路由与图标
- [x] 4.2 Compose 日志轮转；`scripts/ops_probe.sh` 探测 `/ready`
- [x] 4.3 跑 pytest 相关用例与导航冒烟
