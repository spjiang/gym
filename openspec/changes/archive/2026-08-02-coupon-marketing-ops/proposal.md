## Why

零售与会籍已可售卖，但缺少优惠券抵扣能力，无法对齐 PRD §5.5。设计：`docs/superpowers/specs/2026-08-02-coupon-marketing-design.md`。

## What Changes

- 券模板（满减/折扣、门槛、适用 retail/membership/both）
- 后台发券、会员持券
- 零售/办卡下单可选一券；支付核销；退款回退
- 权限、后台页、测试

## Non-goals（仅限本 change）

- 小程序领券、叠加多券、活动价、体验卡、分销、真微信

## Capabilities

### New Capabilities

- `coupon-catalog`: 券模板维护与启停
- `coupon-issuance`: 发券与会员持券查询
- `coupon-redeem`: 下单抵扣、支付核销、退款回退

### Modified Capabilities

- `commerce-skeleton`: 支付/退款钩子处理券状态
- `identity-access`: coupon 权限点

## Impact

后端模型/API/钩子；零售与办卡扩展；前端 `/coupons`；PRD §10
