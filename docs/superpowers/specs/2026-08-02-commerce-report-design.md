# 经营报表看板 MVP 设计

**状态：** 已批准（2026-08-02）  
**Change 建议名：** `commerce-report-ops`  
**对齐 PRD：** §5.6 报表与财务（本切片仅经营汇总 + 流水导出）

## 1. 目标

在 Web 管理后台提供按商户、日期区间的收款/退款/净收汇总，并按支付渠道与业务类型拆分；支持 CSV 流水导出以便对账。

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 范围 | MVP：营业汇总 + 按渠道/业务类型拆分 + CSV；不含会籍/课程/库存指标 |
| 端 | 仅 Web 后台 |
| 权限 | 仅超管与商户管理员（`report:read`）；前台/教练不可见 |
| 实现 | 实时聚合 `payments`（关联 `orders`），无日结快照表 |

## 3. 指标口径

- 时间：`payments.created_at` 落在 `[date_from, date_to]`（含边界日）
- 收款：`kind=charge` 之和；退款：`kind=refund` 之和；净收 = 收款 − 退款
- 拆分：按 `channel`；按订单 `order_type`
- 商户：商户管理员强制本商户；超管可选 `merchant_id` 或全场地

## 4. API 与页面

- `GET /reports/commerce-summary`
- `GET /reports/commerce-payments.csv`
- 后台「经营报表」页：筛选 → 汇总卡片/拆分表 → 导出

## 5. 明确不做

会籍/课程/商品经营指标、会计总账、税务、定时快照、前台可见报表。

## 6. 验收

1. 有支付数据时汇总与 CSV 一致  
2. 商户隔离正确；无 `report:read` 拒绝  
3. 超管可跨商户或按商户筛选  
