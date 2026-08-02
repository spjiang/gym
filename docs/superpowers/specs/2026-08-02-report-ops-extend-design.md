# 报表扩展：会籍 / 课程 / 库存汇总

日期：2026-08-02  
状态：已批准（方案 A）  
对应 change：`report-ops-extend`

## 目标

在既有经营收款汇总之上，补齐 PRD §5.6 的会籍、课程、商品库存看板指标。

## 设计

- `GET /reports/membership-summary`：区间新开/续费；快照在籍/停卡；区间内到期
- `GET /reports/course-summary`：区间团课场次、预约、满课场次；私教核销课时（按已有核销记录）
- `GET /reports/inventory-summary`：区间销量 + 当前 SKU 库存简表（含低库存）
- 权限与商户隔离同现有报表；`ReportsView` 分区展示
- 不做：总账、复杂 Excel、预聚合表

## 验收

pytest 覆盖三接口与商户隔离；PRD §10 报表行更新。
