## ADDED Requirements

### Requirement: 支付与退款处理优惠券状态
系统 SHALL 在支付成功时核销订单绑定券，在全额退款时回退券状态。

#### Scenario: 支付核销
- **WHEN** 绑券订单变为已支付
- **THEN** 券变为 used
