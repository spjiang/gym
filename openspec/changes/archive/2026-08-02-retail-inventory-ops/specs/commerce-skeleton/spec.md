## ADDED Requirements

### Requirement: 支付成功可触发零售履约
系统 SHALL 在 `retail` 订单支付路径中校验库存并在成功支付后扣减库存；库存不足时 MUST NOT 将订单标为已支付。

#### Scenario: 零售支付成功履约
- **WHEN** retail 订单支付校验通过并完成支付
- **THEN** 库存已按行项目扣减

### Requirement: 零售退款可回补库存
系统 SHALL 在 `retail` 已支付订单全额退款时，若此前已履约扣库存，则回补库存。

#### Scenario: 零售退款回补
- **WHEN** 已履约 retail 订单全额退款
- **THEN** 库存回补且订单为已退款
