## Why

经营收款汇总已交付，PRD §5.6 仍缺会籍、课程、库存指标，运营看板不完整。

## What Changes

- 新增会籍 / 课程 / 库存三类报表汇总 API（商户隔离 + 日期区间）
- Web 报表页分区展示
- **不做**：会计总账、复杂 Excel、预聚合仓

## Capabilities

### New Capabilities
- （无独立新能力名；扩展既有报表）

### Modified Capabilities
- `commerce-report`: 增加会籍、课程、库存汇总需求

## Impact

- `services/reports.py`、`api/reports.py`、`ReportsView.vue`、测试
