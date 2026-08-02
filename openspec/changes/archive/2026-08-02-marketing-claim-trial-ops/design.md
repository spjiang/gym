## Context

批准设计见 `docs/superpowers/specs/2026-08-02-marketing-claim-trial-design.md`。复用现有券发放与会籍履约，避免平行实体。

## Goals / Non-Goals

- Goals: 会员自助领券；体验卡标记与售卖展示
- Non-Goals: 活动价、裂变、活动码、短信

## Decisions

- `CouponTemplate.claimable` + `per_member_limit`；领取逻辑抽到 `services/coupon.py` 供员工发券与会员领取共用计数
- `MembershipProduct.is_trial`；履约不变
- 迁移 `20260802_0008`

## Risks / Trade-offs

- 每人限领按会员券行计数（含已用/过期），避免反复白嫖；作废券是否占额度：计入已领（防刷）

## Migration Plan

Alembic 加列默认值，兼容存量数据。
