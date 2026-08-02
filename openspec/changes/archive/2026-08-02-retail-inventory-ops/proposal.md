## Why

会籍与课程已交付，前台仍无法售卖补给/周边并管理库存，无法对齐 PRD §5.4。设计：`docs/superpowers/specs/2026-08-02-retail-inventory-design.md`。

## What Changes

- 商品分类、SKU、库存数量与预警阈值
- 入库/出库/盘点与库存流水；禁止负库存
- 零售订单 `retail`（可关联会员）；支付前校验库存，履约扣减；已履约全额退款回补
- Web 后台独立 `/retail*` 页面与权限点；测试主路径

## 后续切片承诺（不在本 change）

- 会员小程序商城、营销券、完整经营报表、真实微信进件

## Non-goals（仅限本 change）

- 小程序商城、多仓调拨、采购单、批次效期、成本核算、营销券、真实微信联调
- 项目级一期仍不做：酒吧 POS 等（PRD §9）

## Capabilities

### New Capabilities

- `retail-catalog`: 分类与 SKU 维护、启停
- `inventory-stock`: 入出库盘点、流水、低库存预警、非负约束
- `retail-checkout`: 零售下单、支付校验与履约扣库存、退款回补

### Modified Capabilities

- `commerce-skeleton`: `retail` 订单履约/退款回补钩子
- `identity-access`: `retail:manage` / `retail:sell` / `retail:read`

## Impact

- 后端模型/迁移/API/服务；前端零售菜单；seed 权限；PRD §10 回写
