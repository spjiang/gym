## Why

一期剩余缺口：活动价、生产支付/短信通道、原生小程序、Web 菜单按角色细裁。

## What Changes

- 卡种/SKU/私教课包限时活动价，下单取生效价
- Web 侧栏与路由按 permissions 过滤
- 微信支付与短信 OTP 生产适配（凭证驱动；无凭证 503）
- `miniprogram/` 原生工程对接会员 API
- **不做**：无凭证的真实商户联调验通、小程序提审

## Capabilities

### New Capabilities
- `promo-pricing`: 限时活动价
- `member-miniprogram`: 原生小程序工程

### Modified Capabilities
- `commerce-skeleton`: 微信支付模式
- `member-auth`: 短信 OTP 模式
- `identity-access`: 菜单按权限裁剪（前端契约）
- `project-scaffold`: 小程序目录与 env 示例

## Impact

- 模型 0009、支付/OTP 服务、前端 Layout/router、miniprogram、.env.example
