# 会员 H5 多商户业态分流与餐饮闭环 — 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-04 |
| 状态 | 已落地 |
| 关联 | PRD §6.2；餐饮后台闭环；会员门户 `member_portal` / `member-web` |
| 范围 | 会员 H5 + 会员端 API；健身能力复用；餐饮会员点餐支付退款 |
| 非目标 | 桌台 KDS、配送、餐饮券、管理端餐饮大改、原生小程序同步改版（可随后对齐） |

## 1. 背景与目标

会员可跨业态关联多个商户（如健身房 + 清吧），但 H5 仅展示「商户 #id」，功能菜单几乎全是健身能力，无法按业态进入清吧点餐。

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 范围 | **B**：选店 + 业态分流壳 + **会员端完整餐饮闭环** |
| 选店 | 登录后先选关联商户；可随时切换 |
| 健身 | 复用现有 H5 页，挂在 `/m/:merchantId/gym/*` |
| 餐饮 | 菜单、购物车下单、线上支付、订单与取餐号、会员发起退款 |
| 支付 | 复用现有 `/member/orders/{id}/pay/online`（含 mock 通道） |

### 1.2 成功标准

- Demo 会员 `13800001001` 能看到至少一家健身店与一家清吧，并切换。
- 进入清吧：点餐 → 支付 → 见取餐号 → 可申请退款且状态可见。
- 进入健身房：会籍/团课/商城等行为与现网一致。
- 未关联商户或未选店时，不能误入他店数据。

## 2. 信息架构与路由

```
/login
/stores                          # 选店（未选店强制落地）
/m/:merchantId/gym               # 健身首页（功能入口）
/m/:merchantId/gym/memberships|classes|shop|coupons|access|notifications
/m/:merchantId/catering          # 餐饮首页 / 点餐
/m/:merchantId/catering/cart     # 可选：独立购物车（也可同页）
/m/:merchantId/catering/orders
/m/:merchantId/catering/orders/:id
```

顶栏：当前店名、业态标签、「切换店铺」。底栏（或宫格）按业态切换菜单项。

路由守卫：

1. 未登录 → `/login`
2. 已登录无有效 `merchantId` 或不在 `me.merchants` → `/stores`
3. 进入 `gym/*` 要求该商户 `subsystem_codes` 含 `gym`；`catering/*` 同理含 `catering`
4. 若商户同时挂两业态（少见），选店卡片可拆成两个入口或进店后再选业态首页；一期 Demo 店为单业态，默认进唯一业态首页

## 3. API

### 3.1 扩展 `GET /member/me`

```json
{
  "id": 1,
  "site_id": 1,
  "phone": "13800001001",
  "name": "...",
  "face_status": "...",
  "merchant_ids": [1, 2],
  "merchants": [
    {
      "id": 1,
      "name": "回龙观自营健身房",
      "subsystem_codes": ["gym"],
      "primary_system": "gym"
    },
    {
      "id": 2,
      "name": "回龙观清吧",
      "subsystem_codes": ["catering"],
      "primary_system": "catering"
    }
  ]
}
```

- `merchant_ids` **保留**兼容旧客户端。
- `primary_system`：取已挂业务子系统中 sort 最前的一个（`gym` 优先于 `catering` 若双挂，可配置；Demo 单挂无歧义）。

### 3.2 会员餐饮 API（新建，挂 `member` 前缀）

建议实现位置：`systems/catering/api/member_catering.py` 或 `member_portal` 内分组；路径统一 `/api/v1/member/catering/*`。

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/member/catering/menu` | `merchant_id` 必填；仅 `is_active`；校验会员已关联该商户且商户挂 `catering` |
| POST | `/member/catering/checkout` | body: `{ merchant_id, items[{menu_item_id, quantity}], note?, table_no? }` → 创建 `dining` 待支付单 + `CateringOrderItem`；`member_id=本人` |
| GET | `/member/catering/orders` | 本人该商户 dining 订单列表 |
| GET | `/member/catering/orders/{id}` | 详情含行项目、`pickup_code`、支付/退款状态 |
| POST | `/member/catering/orders/{id}/refund` | 已支付可申请；执行与后台一致的退款记账（或置 `refund_requested` 后立即走现有 refund 服务——一期 **直接退款入账** 以闭环可测，审计记 `member.dining_refund`） |

支付：已有 `POST /member/orders/{id}/pay/online`；支付成功后为 dining 单生成/回写 `pickup_code`（若订单表无列则用 `note` JSON 或扩展列，见下）。

### 3.3 取餐号与桌号

| 字段 | 方案 |
|------|------|
| `pickup_code` | 支付成功生成：`C` + `str(order.id).zfill(4)[-4:]`（冲突可加随机位）；落库 |
| `table_no` / `note` | checkout 可选；存订单扩展 |

推荐：`orders` 增加可空列 `pickup_code`（String 16）、`customer_note`（String 255），Alembic 迁移；避免滥用 title。

### 3.4 鉴权

- 一律 `get_current_member`。
- 写操作：`MerchantMember` 存在且 `assert_merchant_has_system(..., "catering")`。
- 读订单：`order.member_id == 本人`。

## 4. 前端（member-web）

| 模块 | 职责 |
|------|------|
| `stores/auth.ts` | `merchants[]`、`merchantId`、选店后按 `primary_system` 跳转 |
| `views/StoresView.vue` | 选店卡片（名、业态标签） |
| `views/LayoutView.vue` | 顶栏店名/切换；底栏按业态 |
| `views/gym/*` | 由现页迁入或 path 参数化 `merchantId` |
| `views/catering/MenuView.vue` | 分类菜单 + 加购 |
| `views/catering/OrdersView.vue` | 订单列表 |
| `views/catering/OrderDetailView.vue` | 详情、支付、退款、取餐号 |

支付：待支付详情点「去支付」→ 调线上支付 → 展示取餐号。

## 5. 数据与迁移

- Alembic：`orders.pickup_code`、`orders.customer_note`（可空）。
- Seed：确保演示会员关联健身房与清吧（已有则不动）。

## 6. 风险与测试

| 风险 | 对策 |
|------|------|
| 健身页硬编码无 `merchantId` | 统一从 auth store 读；路由带 id 同步 store |
| 支付成功未履约 dining | dining 无需会籍履约；仅写 pickup_code |
| 退款被滥用 | 仅 paid→refunded；一单一退；审计 |
| 双业态商户 | 一期 Demo 单业态；API 按路径校验 system |

测试：

1. API：菜单鉴权、checkout、支付后 pickup、退款。
2. H5 手工：两店切换、清吧闭环、健身房回归。

## 7. 实施顺序

1. 迁移订单扩展字段；扩展 `/member/me`。
2. 会员餐饮 API + 支付挂钩取餐号。
3. H5 选店与路由守卫、业态 Layout。
4. 餐饮前端闭环页。
5. 健身路由迁入 `/m/:id/gym`；回归。
6. 文档 `user.md` / PRD §10 回写。
