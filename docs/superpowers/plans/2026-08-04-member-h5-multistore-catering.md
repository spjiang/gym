# 会员 H5 多商户业态分流与餐饮闭环 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 会员 H5 登录后按关联商户选店；按业态进入健身或餐饮；餐饮支持菜单点餐、线上支付、取餐号与会员退款闭环。

**Architecture:** 扩展 `/member/me` 返回商户+子系统；新增 `/member/catering/*`；`orders` 增加 `pickup_code`/`customer_note`；支付成功为 dining 写取餐号。H5 路由改为 `/stores` + `/m/:merchantId/{gym|catering}/*`。

**Tech Stack:** FastAPI · Alembic · Vue 3 · Pinia · Docker Compose（`member-web`）

**Spec:** `docs/superpowers/specs/2026-08-04-member-h5-multistore-catering-design.md`

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 会员写操作必须校验 `MerchantMember` + 业态挂接
- 支付复用现有 online provider；dining 不走会籍/私教履约
- 未要求不 git commit
- 验证：pytest + H5 手工冒烟（`13800001001` / 验证码 `123456`）

## File Map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/20260804_0012_order_pickup_note.py` | `pickup_code`、`customer_note` |
| `backend/app/systems/platform/models/commerce.py` | Order 字段 |
| `backend/app/core/schemas/common.py` | `OrderOut` 扩展 |
| `backend/app/systems/platform/api/member_portal.py` | `/me` 商户列表；支付后写 pickup |
| `backend/app/systems/catering/api/member_catering.py` | 会员餐饮 API |
| `backend/app/main.py` | 挂载 router |
| `backend/tests/test_member_catering.py` | API 闭环测试 |
| `member-web/src/stores/auth.ts` | merchants、进店跳转 |
| `member-web/src/router/index.ts` | 新路由与守卫 |
| `member-web/src/views/StoresView.vue` | 选店 |
| `member-web/src/views/LayoutView.vue` | 业态顶栏底栏 |
| `member-web/src/views/catering/*.vue` | 点餐/订单 |
| `member-web/src/views/*` | 健身页适配 path |
| `user.md` / PRD §10 | 文档 |

---

### Task 1: 订单字段迁移 + OrderOut

**Files:**
- Create: `backend/alembic/versions/20260804_0012_order_pickup_note.py`（`down_revision = "20260804_0011"`）
- Modify: `backend/app/systems/platform/models/commerce.py`
- Modify: `backend/app/core/schemas/common.py`（`OrderOut`）

- [x] **Step 1: 模型增加字段**

```python
# Order 类内
pickup_code: Mapped[str | None] = mapped_column(String(16), nullable=True)
customer_note: Mapped[str | None] = mapped_column(String(255), nullable=True)
```

- [x] **Step 2: Alembic upgrade 加列（Postgres/SQLite 兼容）**

```python
op.add_column("orders", sa.Column("pickup_code", sa.String(16), nullable=True))
op.add_column("orders", sa.Column("customer_note", sa.String(255), nullable=True))
```

- [x] **Step 3: `OrderOut` 增加 `pickup_code: str | None = None`、`customer_note: str | None = None`**

- [x] **Step 4: 迁移在 compose 启动时自动执行；本地可 `alembic upgrade head`**

---

### Task 2: 扩展 `/member/me` + 会员餐饮 API + 支付取餐号

**Files:**
- Modify: `backend/app/systems/platform/api/member_portal.py`
- Create: `backend/app/systems/catering/api/member_catering.py`
- Modify: `backend/app/main.py`
- Create: `backend/tests/test_member_catering.py`

**Interfaces:**
- `MemberMerchantOut(id, name, subsystem_codes, primary_system)`
- `MemberMeOut.merchants: list[MemberMerchantOut]`
- `ensure_member_merchant(db, member_id, merchant_id)` + `assert_merchant_has_system`
- `assign_pickup_code(order) -> str`：`C` + 末 4 位订单号

- [x] **Step 1: `/member/me` 组装 merchants**

```python
from app.core.domain.subsystems import merchant_subsystem_codes
from app.systems.platform.models.org import Merchant

# primary: 业务子系统优先 gym > catering > 其它
def _primary_system(codes: list[str]) -> str | None:
    for c in ("gym", "catering"):
        if c in codes:
            return c
    return codes[0] if codes else None
```

- [x] **Step 2: `member_catering.py` 实现 menu / checkout / orders / refund**

Checkout 逻辑对齐后台 `catering.checkout`，但 `member_id=mctx.member.id`，`customer_note` 拼接 `table_no`+`note`。

Refund：仅 `paid`；写 `Payment(kind=refund)`；`status=refunded`；审计 `member.dining_refund`。

- [x] **Step 3: `pay_my_order_online` 成功后**

```python
if order.order_type == "dining" and not order.pickup_code:
    order.pickup_code = f"C{str(order.id).zfill(4)[-4:]}"
```

勿对 dining 调用会籍/私教 fulfill（已有调用应 no-op；确认 fulfill 函数对非目标类型直接 return）。

- [x] **Step 4: 测试**（会员 OTP 登录夹具沿用 `test_member_h5`）

```python
def test_member_dining_checkout_pay_refund(client, member_headers, bar_merchant_id):
    menu = client.get("/api/v1/member/catering/menu", params={"merchant_id": bar_merchant_id}, headers=member_headers)
    assert menu.status_code == 200 and len(menu.json()) >= 1
    item_id = menu.json()[0]["id"]
    order = client.post("/api/v1/member/catering/checkout", headers=member_headers, json={
        "merchant_id": bar_merchant_id,
        "items": [{"menu_item_id": item_id, "quantity": 1}],
        "note": "少冰",
    }).json()
    assert order["status"] == "pending"
    paid = client.post(f"/api/v1/member/orders/{order['id']}/pay/online", headers=member_headers).json()
    assert paid["status"] == "paid" and paid["pickup_code"]
    refunded = client.post(f"/api/v1/member/catering/orders/{order['id']}/refund", headers=member_headers).json()
    assert refunded["status"] == "refunded"
```

- [x] **Step 5: 跑测** `pytest tests/test_member_catering.py -q`

---

### Task 3: H5 选店 + 路由守卫 + Layout

**Files:**
- Modify: `member-web/src/stores/auth.ts`
- Create: `member-web/src/views/StoresView.vue`
- Modify: `member-web/src/router/index.ts`
- Modify: `member-web/src/views/LayoutView.vue`

- [x] **Step 1: auth 类型与 `enterStore(m)`**

```ts
export type MemberMerchant = {
  id: number
  name: string
  subsystem_codes: string[]
  primary_system: string | null
}
// fetchMe 后若无 merchantId，跳转 stores（由路由守卫处理）
function enterPathFor(m: MemberMerchant) {
  const sys = m.primary_system || m.subsystem_codes[0]
  if (sys === 'catering') return `/m/${m.id}/catering`
  return `/m/${m.id}/gym`
}
```

- [x] **Step 2: 路由**

```ts
{ path: '/stores', name: 'stores', component: StoresView },
{
  path: '/m/:merchantId',
  component: LayoutView,
  children: [
    { path: 'gym', name: 'gym-home', component: HomeView },
    { path: 'gym/memberships', ... },
    // ... 其它健身页
    { path: 'catering', name: 'catering-menu', component: CateringMenuView },
    { path: 'catering/orders', name: 'catering-orders', component: CateringOrdersView },
    { path: 'catering/orders/:orderId', name: 'catering-order', component: CateringOrderDetailView },
  ],
}
```

守卫：同步 `route.params.merchantId` → `setMerchantId`；校验 merchants 列表与 subsystem。

- [x] **Step 3: Layout 按 path 含 `/catering` 切换 tab**

健身 tabs：首页/会籍/团课/商城/卡券/通行  
餐饮 tabs：点餐/订单 + 顶栏「切换店铺」→ `/stores`

- [x] **Step 4: StoresView 卡片展示 name + 业态标签，点击 `enterStore`**

---

### Task 4: 餐饮前端闭环页

**Files:**
- Create: `member-web/src/views/catering/MenuView.vue`
- Create: `member-web/src/views/catering/OrdersView.vue`
- Create: `member-web/src/views/catering/OrderDetailView.vue`

- [x] **Step 1: MenuView** — 拉菜单、本地 cart、提交 checkout → 跳转订单详情  
- [x] **Step 2: OrderDetailView** — 行项目、状态、取餐号；pending 显示支付；paid 显示退款  
- [x] **Step 3: OrdersView** — 列表进详情  
- [x] **Step 4: 重建 member-web 镜像并手工点通**

---

### Task 5: 健身页路径适配 + 文档

**Files:**
- Modify: 现有 `HomeView` 等（`RouterLink` 改为带 `merchantId` 的路径，或相对当前路由）
- Modify: `user.md`、`README.md`
- Modify: PRD §10 一行进度
- Modify: spec 状态 → 已落地

- [x] **Step 1: 所有内部链接使用 `` `/m/${auth.merchantId}/gym/...` ``**  
- [x] **Step 2: 兼容旧书签：`/` 已登录有商户则重定向到对应业态首页，否则 `/stores`**  
- [x] **Step 3: 文档写明 H5 选店与清吧点餐验收路径**  
- [x] **Step 4: `docker compose up --build -d member-web backend` 冒烟**

---

## Spec coverage

| Spec | Task |
|------|------|
| me.merchants | 2 |
| catering API + pickup + refund | 2 |
| 选店/路由/Layout | 3 |
| 餐饮 UI | 4 |
| 健身路径 + 文档 | 5 |
| 迁移字段 | 1 |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-04-member-h5-multistore-catering.md`.

**Two execution options:**

1. **Subagent-Driven（推荐）** — 每任务独立子代理  
2. **Inline Execution** — 本会话连续做完  

Which approach?
