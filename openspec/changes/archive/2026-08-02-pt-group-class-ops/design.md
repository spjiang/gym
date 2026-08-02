## Context

会籍与门禁已归档。本 change 交付 Web 后台私教/团课闭环。详细设计见 `docs/superpowers/specs/2026-08-02-pt-group-class-design.md`，实现计划见 `docs/superpowers/plans/2026-08-02-pt-group-class-ops.md`。

## Goals / Non-Goals

**Goals:**

- 教练档案、私教课包售卖履约与核销
- 团课模板/场次/改派、后台代约取消、签到
- 满员不可约；约课需本商户生效会籍
- 教练仅本人数据；关键操作审计；测试覆盖主路径

**Non-Goals（仅限本 change）：**

- 小程序约课购课、候补、真实微信进件、库存营销报表器材、门禁自动签到、次卡约团课扣次

## Decisions

### 1. 模型落在 `backend/app/models/course.py`

表：`coaches`、`pt_package_products`、`pt_package_product_coaches`、`pt_packages`、`pt_order_links`、`group_courses`、`group_sessions`、`group_bookings`。

### 2. 履约对齐会籍

- `order_type=pt_package`；支付成功调用 `pt_fulfillment.fulfill_pt_package_order`
- 关联表 `pt_order_links` 记录履约结果与 `fulfill_error`

### 3. 预约防超卖

- `book_group_session`：事务内 `SELECT ... FOR UPDATE` 锁场次行，统计 `booked` 数与 capacity 比较
- 会籍：`Membership.status=active` 且未过 `ends_at`（期限卡）或等效生效判断

### 4. 权限

- `coach:manage` / `course:manage` / `course:book` / `course:checkin` / `pt:sell`
- 教练角色：`course:checkin` + 本人范围过滤

### 5. 前端

- 页面：教练、私教课包、团课、教练工作台；风格对齐现有 Memberships/Orders

## Risks / Trade-offs

- [并发超卖] → 行锁 + 唯一/应用校验  
- [履约失败] → 订单保持已支付，错误可追踪  
- [教练与员工脱节] → 创建绑定 staff；停用不可排新场  

## Migration Plan

- Alembic `20260802_0003_course.py`；seed 合并权限  

## Open Questions

- 无（决策已在设计规格确认）
