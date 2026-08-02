## Purpose

定义一单一券抵扣、支付核销与退款回退。

## ADDED Requirements

### Requirement: 下单可选用一张券抵扣
系统 SHALL 允许零售或会籍办卡订单绑定一张适用券并计算实付；不满足门槛或适用类型时 MUST 拒绝。

#### Scenario: 满减后实付正确
- **WHEN** 原价满足门槛且使用满减券下单
- **THEN** 订单金额为抵扣后实付（不低于 0.01）

### Requirement: 支付成功核销券
系统 SHALL 在订单支付成功后将绑定券标记为已使用。

#### Scenario: 支付后券已用
- **WHEN** 绑券订单支付成功
- **THEN** 对应会员券状态为 used

### Requirement: 退款回退券
系统 SHALL 在全额退款时将已用券恢复为 unused，若已过期则标记 expired。

#### Scenario: 退款后券可再用
- **WHEN** 绑券已支付订单全额退款且券仍在有效期内
- **THEN** 券状态恢复为 unused
