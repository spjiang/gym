## Context

见设计规格。一单一券；支付成功核销。

## Goals / Non-Goals

Goals: 模板、发券、零售/办卡抵扣、核销与退款回退。  
Non-Goals: 小程序、叠加、活动价、体验卡。

## Decisions

1. 表：coupon_templates、member_coupons、order_coupon_links  
2. compute_payable 统一计价；最低 0.01  
3. 支付钩子 redeem；退款 restore  
4. 前台含 manage+redeem+read

## Risks

并发核销行锁；退款过期标 expired。

## Migration Plan

Alembic 20260802_0005_coupon.py

## Open Questions

无
