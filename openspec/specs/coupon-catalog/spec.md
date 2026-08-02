## Purpose

定义优惠券模板的创建、配置与启停。

## Requirements

### Requirement: 配置优惠券模板
系统 SHALL 允许创建券模板，包含满减或折扣、门槛、适用业务范围、有效期，以及是否可自助领取与每人限领数量。

#### Scenario: 创建满减券
- **WHEN** 管理员提交合法满减券模板
- **THEN** 系统保存且可发放

#### Scenario: 创建可领券
- **WHEN** 管理员创建 claimable=true 且 per_member_limit>=1 的模板
- **THEN** 模板可供会员自助领取
