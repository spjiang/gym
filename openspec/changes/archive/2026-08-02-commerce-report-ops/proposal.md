## Why

PRD §5.6 要求按商户查看经营汇总与可对账流水；订单/支付已落地，管理端仍缺汇总与导出能力，运营无法快速看清收款、退款与净收。

## What Changes

- 新增经营汇总 API：按日期区间统计收款、退款、净收，并按支付渠道与业务类型拆分
- 新增支付流水 CSV 导出
- 后台增加「经营报表」页
- 新增权限点 `report:read`，仅超管与商户管理员
- **仅限本 change 不做**：会籍/课程/库存经营指标、会计总账、税务、日结快照、前台可见报表

## Capabilities

### New Capabilities
- `commerce-report`: 经营汇总查询与支付流水 CSV 导出

### Modified Capabilities
- `identity-access`: 增加 `report:read` 权限点及角色分配范围

## Impact

- 后端：`reports` API、聚合查询、seed 权限
- 前端：`ReportsView` + 菜单
- 测试：汇总口径、商户隔离、无权限拒绝
- 设计：`docs/superpowers/specs/2026-08-02-commerce-report-design.md`
