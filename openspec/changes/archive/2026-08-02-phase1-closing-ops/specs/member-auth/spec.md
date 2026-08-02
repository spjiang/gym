## ADDED Requirements

### Requirement: 短信验证码通道
系统 SHALL 支持会员 OTP 以 mock 或 http 短信通道发送；http 模式下验证码须按发送记录校验。

#### Scenario: http 模式发送并校验
- **WHEN** OTP 模式为 http 且短信网关配置可用
- **THEN** 系统生成验证码并仅接受该次发送的码
