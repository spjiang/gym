# 优惠券营销（Web 后台）— 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-02 |
| 状态 | 已批准 |
| 依据 PRD | `docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` §5.5 |
| 推进方式 | 单 OpenSpec change 交付后台优惠券闭环（方案 1） |
| 建议 change 名 | `coupon-marketing-ops` |

## 1. 已确认决策

- 仅 Web 后台；不做小程序领券
- 仅优惠券（不做活动价、体验卡）
- 一单一券不可叠加；可用于零售与/或会籍办卡
- 类型：满减 `fixed` / 折扣 `percent`；最低实付 0.01
- 支付成功才核销；全额退款回退券状态

## 2. 范围

### 做

- 券模板、发券、会员持券查询
- 零售订单 / 会籍办卡订单可选一券抵扣
- 支付核销、退款回退；权限审计测试

### 不做

- 小程序、叠加多券、活动价、体验卡、分销、真微信

## 3. 领域模型

- `CouponTemplate`：类型、门槛、面额/折扣、applicable_to（retail/membership/both）、有效期、总量、启停
- `MemberCoupon`：unused/used/expired/void；核销关联 order
- `OrderCouponLink`：一单一券 + 抵扣金额

## 4. 流程

建模板 → 发券 → 下单带 `member_coupon_id`（校验不核销）→ 支付成功核销 → 退款回退（过期则 expired）

## 5. 权限 / API / UI

- 权限：`coupon:manage` / `coupon:redeem` / `coupon:read`
- API：`/coupons/templates`、`/coupons/issue`、会员持券；零售/办卡扩展可选券
- 前端：`/coupons`；收银与办卡页选券

## 6. 验收

建发券、抵扣金额正确、门槛/适用拒绝、支付核销、退款回退、测试覆盖。

## 7. 下一步

审阅通过后：`/opsx-propose` → `coupon-marketing-ops` → apply → archive → 回写 PRD §10。
