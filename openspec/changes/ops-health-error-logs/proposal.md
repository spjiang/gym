## Why

线上仅靠进程探活和操作审计，无法区分「业务拒单」与「通道/程序故障」：支付回调失败几乎不落库，500 没有堆栈可查，数据库挂了 `/health` 仍可能报 ok。需要在运维管理里同时看到服务是否就绪、系统错误，并用 `request_id` 对上操作日志。

## What Changes

- 公开探活拆成 `GET /health`（进程存活）与 `GET /ready`（Postgres 就绪；MinIO 降级不影响整体 fail）
- 每个请求生成 `request_id`，回写 `X-Request-ID`；`audit_logs` 增加该列
- 新增 `error_events` 表与运维「错误日志」页：未捕获异常、5xx、支付通道/回调/履约失败、建单中途系统失败
- 业务 4xx（校验、余额/权限、用户未支付）只进操作日志的 failure 详情，不进错误表
- 运维管理新增「服务状态」「错误日志」；权限 `devops:read`（场地管理员默认有 `*`，场地运营人员授予）
- 生产 Compose 为容器日志配置 json-file 轮转；错误事件默认保留 30 天

## Capabilities

### New Capabilities

- `ops-observability`: 服务探活/探就绪、请求追踪、系统错误采集与运维后台查询

### Modified Capabilities

- （无）操作审计既有能力不变，仅增加 `request_id` 关联列

## Impact

- 后端：FastAPI 中间件与全局异常、`error_events` 迁移、支付回调主动记错、平台 manifest/种子权限
- 前端：运维管理菜单与两个新页面
- 部署：`docker-compose.yml` / `docker-compose.prod.yml` 日志轮转；探活脚本可选
- 不影响门禁开门路径与会员支付主流程的业务语义
