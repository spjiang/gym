## Context

临访复用 AccessGrant；本切片加 visit_passes 业务记录。

## Goals / Non-Goals

Goals: 时段临访 + 撤销 + Web。  
Non-Goals: 次数扣减、体验卡销售。

## Decisions

1. visit_passes 关联 grant_id  
2. 有效期用 hours 计算 valid_until  
3. 权限复用 access:manage

## Migration Plan

Alembic 0007_visit.py

## Open Questions

无。
