## Purpose

定义按商户与日期区间的经营收款汇总及支付流水导出，支撑对账与经营看板。

## ADDED Requirements

### Requirement: 经营收款汇总
系统 SHALL 按日期区间汇总支付流水的收款、退款与净收，并按支付渠道与订单业务类型拆分；结果 MUST 受商户隔离约束。

#### Scenario: 查询本商户汇总
- **WHEN** 商户管理员提交合法日期区间查询经营汇总
- **THEN** 系统返回本商户收款、退款、净收及拆分数据

#### Scenario: 超管可按商户筛选
- **WHEN** 场地超管指定 merchant_id 查询汇总
- **THEN** 系统仅聚合该商户流水

### Requirement: 导出支付流水 CSV
系统 SHALL 支持按相同过滤条件导出支付流水 CSV，字段足以核对单笔收款/退款。

#### Scenario: 导出成功
- **WHEN** 有权限用户请求导出 CSV
- **THEN** 系统返回包含订单与支付关键字段的 CSV 文件
