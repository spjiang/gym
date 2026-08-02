## ADDED Requirements

### Requirement: 微信支付生产模式
系统 SHALL 支持 ONLINE_PAYMENT_MODE=wechat；凭证齐全时可创建支付单，凭证缺失 MUST 返回明确未配置错误。

#### Scenario: 缺凭证拒绝
- **WHEN** 模式为 wechat 但缺少商户配置
- **THEN** 线上支付返回不可用错误
