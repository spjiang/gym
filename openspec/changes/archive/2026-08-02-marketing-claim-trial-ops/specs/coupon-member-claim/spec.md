## Purpose

会员自助领取优惠券与查询持券。

## ADDED Requirements

### Requirement: 会员领取可领券
系统 SHALL 允许会员对启用且标记可领的券模板领取，并遵守每人限领与发放总量上限。

#### Scenario: 领取成功
- **WHEN** 会员对可领模板首次领取且未超限
- **THEN** 生成 unused 会员券且模板已发数量加一

#### Scenario: 超每人限领拒绝
- **WHEN** 会员对该模板已达 per_member_limit
- **THEN** 系统拒绝领取

### Requirement: 会员查询可领与持券
系统 SHALL 允许会员按商户查看当前可领模板列表与本人持券。

#### Scenario: 列出可领券
- **WHEN** 会员请求可领列表
- **THEN** 仅返回启用、可领且在有效期内的模板
