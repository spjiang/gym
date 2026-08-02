## Context

见 proposal。门禁设备属平台层；本切片为健身房业态器材。

## Goals / Non-Goals

Goals: 台账 CRUD、报修流转、权限、Web 页。  
Non-Goals: IoT、约器械、复杂工单、完整调拨史。

## Decisions

1. 表 `equipment_assets`、`equipment_repair_tickets`
2. 状态枚举：in_use / repair / disabled / scrapped
3. 报修创建默认将资产置 repair；完成时可恢复 in_use 或 disabled
4. 权限：manage=商管；repair+read=前台/教练

## Risks

并发改状态 → 以最后写为准；一期可接受。

## Migration Plan

Alembic 0006_equipment.py

## Open Questions

无。
