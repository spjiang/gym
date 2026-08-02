## MODIFIED Requirements

### Requirement: 可扩展订单
系统 SHALL 支持创建归属商户的订单，订单包含类型字段（可扩展，如零售占位、会籍 `membership`、后续课包等），以及金额与状态。

#### Scenario: 创建待支付订单
- **WHEN** 有权限的员工为某商户创建一笔合法订单
- **THEN** 系统保存订单且初始状态为待支付（或等效未完成支付状态）

#### Scenario: 创建会籍订单
- **WHEN** 办卡流程创建类型为 `membership` 的订单
- **THEN** 系统保存该订单且类型标识为 membership，供支付成功后履约会籍

## ADDED Requirements

### Requirement: 支付成功可触发会籍履约
系统 SHALL 在 `membership` 订单支付成功时触发会籍履约（创建或续期会籍）；履约失败 MUST 可追踪且不得静默丢失支付事实。

#### Scenario: 支付成功后履约成功
- **WHEN** membership 订单从待支付变为已支付且履约成功
- **THEN** 对应会籍处于生效（或按续卡规则更新后的有效）状态
