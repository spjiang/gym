## Why

平台底座已具备会员主档、门禁授权与订单支付骨架，但健身房尚不能办卡开通行。需要落地会籍卡种与办卡/续费闭环，使支付成功后会籍生效并自动同步门禁，对齐 PRD `docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` 第 5.1 节与一期成功标准。

## What Changes

- 新增会籍卡种配置（期限卡、次卡、储值卡）：价格、有效期/次数、适用门禁范围、停卡/转卡规则开关
- 新增会籍实例生命周期：办卡、续卡、升级（可先做办卡+续卡）、生效/即将到期/过期/冻结停卡/作废
- 办卡/续卡走统一订单（`order_type=membership`）→ 线下登记或线上支付（沿用现有 Provider：unconfigured/mock，并为微信对接留扩展点）→ 会籍生效
- 会籍生效/失效/停卡自动写入或收回门禁授权，并触发既有异步同步骨架
- 管理后台：卡种管理、会员办卡/续费、会籍列表与停卡操作（前台/商户管理员可用）
- 操作审计：办卡、停卡、作废等关键写操作留痕

## Non-goals（仅限本 change）

- 不做私教/团课、商品库存、营销券、报表、器材台账
- 不做会员小程序/H5 购卡页（本切片完成后可单独开 change；本 change 完成后台闭环）
- 不做真实微信商户进件与生产联调（可完善 mock；生产通道后续支付切片）
- 不做复杂升级换算引擎（若做升级，仅支持简单换新产品种+补差价或二期细化）
- 不做酒吧等非健身业态会籍

## Capabilities

### New Capabilities

- `membership-catalog`: 健身房商户卡种定义与规则配置
- `membership-lifecycle`: 会籍办卡/续卡、状态机、停卡与审计
- `membership-access-link`: 会籍与门禁授权的开通/收回联动

### Modified Capabilities

- `commerce-skeleton`: 明确支持 `membership` 订单类型，并在支付成功后可触发会籍履约钩子（行为增量）

## Impact

- 后端新增 gym 业态模块（models/api/services）、Alembic 迁移、测试
- 前端管理后台新增卡种与会籍相关页面
- 依赖既有：`member-profile`、`access-control`、`commerce-skeleton`、`identity-access`
- 为后续课程预约（校验有效会籍）与小程序购卡提供数据与 API 基础
