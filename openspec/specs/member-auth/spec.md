## Purpose

定义会员端手机号验证码登录与会员访问令牌，并与员工鉴权严格隔离。

## Requirements

### Requirement: 会员验证码登录
系统 SHALL 支持已建档会员通过手机号获取验证码并校验登录；开发环境 MUST 支持可配置的 mock 验证码；未建档手机号 MUST 拒绝并提示到前台开卡。

#### Scenario: 已建档会员登录成功
- **WHEN** 会员提交已存在的手机号与正确验证码
- **THEN** 系统返回会员访问令牌

#### Scenario: 未建档手机号拒绝
- **WHEN** 客户端对未建档手机号请求登录
- **THEN** 系统拒绝并提示需前台开卡

### Requirement: 会员令牌与员工令牌隔离
系统 SHALL 签发可识别为会员的访问令牌；员工令牌 MUST NOT 访问会员端受保护接口，会员令牌 MUST NOT 访问员工管理接口。

#### Scenario: 员工令牌访问会员接口被拒
- **WHEN** 使用员工访问令牌请求会员端受保护 API
- **THEN** 系统返回未授权或禁止访问

### Requirement: 短信验证码通道
系统 SHALL 支持会员 OTP 以 mock 或 http 短信通道发送；http 模式下验证码须按发送记录校验。

#### Scenario: http 模式发送并校验
- **WHEN** OTP 模式为 http 且短信网关配置可用
- **THEN** 系统生成验证码并仅接受该次发送的码
