## Context

见 `docs/superpowers/specs/2026-08-02-retail-inventory-design.md`。复用订单支付钩子，独立 `retail` 域。

## Goals / Non-Goals

**Goals:** 分类/SKU、库存操作与预警、零售收银扣库存、禁止超卖、退款回补、后台 UI 与测试。

**Non-Goals:** 小程序商城、多仓采购、营销、真微信。

## Decisions

1. 模型：`product_categories`、`retail_skus`、`stock_movements`、`retail_order_links`、`retail_order_items`
2. 库存整数非负；支付前校验 + 履约 FOR UPDATE
3. 待支付不锁库存
4. 前台权限含 manage+sell+read；教练无
5. 路由 `/retail` 与会籍 Products 分离

## Risks / Trade-offs

- 待支付期间库存被买光 → 支付失败（可接受）
- 退款回补仅全额且已履约

## Migration Plan

- Alembic `20260802_0004_retail.py`；seed 权限合并

## Open Questions

- 无
