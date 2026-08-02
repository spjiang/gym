## Context

见 proposal 与 `docs/superpowers/specs/2026-08-02-commerce-report-design.md`。支付流水已写入 `payments`，关联 `orders`。

## Goals / Non-Goals

**Goals:** 实时汇总 API、CSV 导出、后台看板、`report:read`。  
**Non-Goals:** 日结表、会籍/课程/库存报表、总账税务、前台开放。

## Decisions

1. **基于 Payment 聚合** — 与对账事实一致；净收 = charge − refund。  
2. **时间取 payment.created_at** — 反映实际入账/退款发生时点。  
3. **权限 `report:read`** — 仅 merchant_admin + site_admin；不用 order:read 以免前台越权看经营看板。  
4. **CSV 同步生成** — 一期数据量小，无需异步任务。

## Risks / Trade-offs

- [大数据量查询变慢] → 后续加索引/缓存或日结；本期接受实时 SQL  
- [时区边界] → API 约定 UTC 或文档说明按服务器时区日界  

## Migration Plan

无 schema 迁移；seed 合并权限；回滚去掉路由与菜单即可。

## Open Questions

无。
