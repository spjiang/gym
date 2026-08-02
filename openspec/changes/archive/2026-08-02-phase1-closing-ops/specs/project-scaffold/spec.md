## ADDED Requirements

### Requirement: 仓库包含小程序与生产通道配置示例
系统 SHALL 在根目录提供 miniprogram 工程与 .env.example 中微信/短信相关配置项说明。

#### Scenario: 示例可复制
- **WHEN** 新环境按 .env.example 配置
- **THEN** 可见 ONLINE_PAYMENT_MODE=wechat 与 OTP 模式相关键
