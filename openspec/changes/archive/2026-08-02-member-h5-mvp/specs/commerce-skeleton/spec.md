## ADDED Requirements

### Requirement: 会员可对本人订单发起线上支付
系统 SHALL 允许已登录会员对其本人创建的待支付订单发起线上支付；支付结果策略与通道配置约束与员工侧线上支付一致，支付成功后 MUST 触发对应订单类型履约。

#### Scenario: 会员线上支付成功履约
- **WHEN** 会员对本人 membership 或 pt_package 待支付订单发起线上支付且通道成功
- **THEN** 订单变为已支付并完成对应履约
