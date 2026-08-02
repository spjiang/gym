## ADDED Requirements

### Requirement: 支付成功可触发私教课包履约
系统 SHALL 在 `pt_package` 订单支付成功时触发私教课包履约；履约失败 MUST 可追踪且不得静默丢失支付事实。

#### Scenario: 支付成功后履约成功
- **WHEN** pt_package 订单从待支付变为已支付且履约成功
- **THEN** 对应课包实例处于生效状态且剩余课时正确
