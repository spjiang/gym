## Why

PRD §6.2 与成功标准要求会员端可完成查卡、约团课、购卡/买课与支付；后台能力已齐，缺少面向会员的 H5 触点与会员鉴权 API。本切片先交付 Vue H5 MVP，打通 C 端闭环，微信原生小程序与真短信/真支付后续切片。

## What Changes

- 新增独立工程 `member-web/`（Vue3 移动端 H5）并纳入 Docker Compose
- 新增会员鉴权：手机号验证码（开发期 mock）、会员 JWT（与员工 token 隔离）
- 新增 `/api/v1/member/*`：本人会籍/课包、团课预约取消、购卡/买课包、线上 mock 支付、通行记录
- 复用现有履约与约课领域服务；不改后台员工端主流程
- **仅限本 change 不做**：微信小程序、短信真发、自助注册、领券/用券、零售商城、约私教、真微信生产支付

## Capabilities

### New Capabilities
- `member-auth`: 会员验证码登录与会员 JWT 鉴权
- `member-portal`: 会员端查询会籍/课包、约团课、购卡买课、支付与通行记录的 API 与 H5 行为

### Modified Capabilities
- `commerce-skeleton`: 明确会员侧可对本人待支付订单发起线上支付并触发既有履约
- `project-scaffold`: Compose 增加 `member-web` 服务

## Impact

- 新增：`member-web/`、`backend/app/api/member_*.py`（或等价模块）、会员 OTP/JWT 依赖
- 修改：`docker-compose.yml`、`.env.example`、可能的 nginx/CORS 配置
- 测试：会员登录、本人范围隔离、约课与购卡支付履约
- 文档：设计见 `docs/superpowers/specs/2026-08-02-member-h5-design.md`；归档后回写 PRD §10
