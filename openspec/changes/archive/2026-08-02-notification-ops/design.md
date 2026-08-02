## Context

轻量站内通知；短信/微信后接。

## Decisions

1. notifications 表：audience=member|staff，member_id 可空，merchant_id，event_type，title，body  
2. write_notification 服务；在 commerce pay、book_group_session、fulfill_membership 钩子调用  
3. GET /notifications（员工）、GET /member/notifications

## Migration Plan

Alembic 0008_notification.py（若与 visit 同批可合并为 0007 两表——分开更清晰）

## Open Questions

无。
