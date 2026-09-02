## Context

现有 `GET /health` 只返回 `{"status":"ok"}`；生产 Compose 已有 `restart: unless-stopped`。写操作经 `AuditMiddleware` 落入 `audit_logs`，后台「运维管理」目前仅「操作日志」。全局异常处理不记录堆栈；支付回调大量 `return FAIL` 而不抛错。见 proposal.md。

## Goals / Non-Goals

**Goals:**
- 探活/探就绪分离，运维页展示 Postgres / API / MinIO
- `request_id` 串联审计与错误事件
- 错误表 + 运维两个新页面；支付回调与 5xx 必进表
- 容器日志轮转，错误事件 30 天清理

**Non-Goals（仅限本 change）：**
- 不上 Loki / Sentry / Prometheus / 企业微信告警机器人
- 不改支付成功主路径与门禁开门路径
- 不把错误中心做成通用 APM

## Decisions

1. **公开探活 vs 后台详情**  
   `/health`、`/ready` 无登录；`GET /api/v1/ops/health-status` 需 `devops:read`。Compose `healthcheck` 继续打 `/health`。  
   备选：healthcheck 改 `/ready` → 数据库抖动会把 backend 标 unhealthy，前端 depends_on 受影响。否决。

2. **错误表与审计表分离**  
   `error_events` 存系统故障；`audit_logs` 只加 `request_id`，failure 的 `detail_json` 补 `error_code`/`message`。  
   备选：全进审计 → 堆栈污染操作留痕。否决。

3. **哪些 AppError 进错误表**  
   - HTTP status ≥ 500  
   - 错误码属于支付系统集合：`wechat_api_error`、`wechat_unconfigured`、`wechat_notify_invalid`、`wechat_notify_rejected`、`online_payment_unconfigured`、`online_pay_failed`、`amount_mismatch`  
   - 回调路径主动 `record_error`（含非法 JSON、找不到 intent、履约失败）  
   其余 4xx AppError 只审计。

4. **写入使用独立 Session**  
   避免业务 rollback 带走错误记录。`record_error` 失败只打 stdout，不得影响原响应（尤其微信回调）。

5. **权限**  
   新权限 `devops:read`。`site_admin` 已有 `*`；`site_ops` 种子授予。财务/健身房管理员默认不授。

6. **日志**  
   异常 structured 打 stdout；Compose `json-file` `max-size: 10m` `max-file: 5`。不引入新采集组件。

## Risks / Trade-offs

- [回调记错失败] → 独立 try/except + stdout，保证仍回微信 FAIL  
- [错误表膨胀] → 30 天写入时清理；堆栈截断 8KB  
- [测试环境 MinIO] → `/ready` 不因 MinIO 失败而 503，测试不额外变脆  
- [门禁延迟] → 错误写入异步于响应返回之前同步写库，单条 insert，不开队列；失败吞掉

## Migration Plan

1. Alembic：`audit_logs.request_id`、`error_events`  
2. 部署后 `sync_manifests` / 种子同步菜单与 `devops:read`  
3. 回滚：保留表无害；可停用菜单

## Open Questions

无。告警通道留待后续 change。
