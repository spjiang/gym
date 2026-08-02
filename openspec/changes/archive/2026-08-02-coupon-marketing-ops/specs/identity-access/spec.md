## ADDED Requirements

### Requirement: 优惠券权限点
系统 SHALL 提供 `coupon:manage`、`coupon:redeem`、`coupon:read` 并校验。

#### Scenario: 无权限不可发券
- **WHEN** 无 coupon:manage 的员工尝试发券
- **THEN** 系统拒绝
