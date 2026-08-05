# 支付退款加固（方案 3）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 支付回调防伪与查单确认；微信原路退/线下退款；会籍课包按剩余价值退并终止权益；对账补单台；移除会员餐饮自助退。

**Architecture:** 强化 `payment_intents` 回调验签解密与查单履约；新增 `refund_intents` + preview 计价 + 退款编排；订单 `refunded_amount`；管理端对账台处理异常单；DRY_RUN 全路径可测。

**Tech Stack:** FastAPI · SQLAlchemy · Alembic · cryptography（AEAD）· httpx · Vue Element Plus · member-web / miniprogram

**Spec:** `docs/superpowers/specs/2026-08-05-payment-refund-hardening-design.md`

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 非 `dry_run` 禁止明文伪造 notify 履约
- 会籍/课包：非 force 金额必须等于 `suggested_amount`；成功后退款终止剩余权益
- 零售部分退不自动回补库存；全额退回补
- 删除会员餐饮自助退 API 与按钮
- 未要求不 git commit
- 验证：pytest 覆盖伪造回调、preview 计价、原路/线下退、对账强制操作权限

## File Map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/20260805_0015_payment_refund_hardening.py` | `refunded_amount`、`refund_intents`、intent 状态扩展 |
| `backend/app/systems/platform/models/commerce.py` | Order.refunded_amount |
| `backend/app/systems/platform/models/payment_settings.py` | RefundIntent；PaymentIntent 状态 |
| `backend/app/systems/platform/services/wechat_pay.py` | 验签、解密、查单、退款、查退款 |
| `backend/app/systems/platform/services/refunds.py` | preview 计价、发起退款、成功落账与权益终止 |
| `backend/app/systems/platform/services/order_fulfill.py` | 保持；退款回滚另在 refunds |
| `backend/app/systems/platform/api/payment_notify.py` | 支付/退款回调加固 |
| `backend/app/systems/platform/api/commerce.py` | refund/preview、pay/query、退款改造 |
| `backend/app/systems/platform/api/member_portal.py` | member pay/query；轮询契约 |
| `backend/app/systems/platform/api/payment_reconcile.py` | 对账台 API |
| `backend/app/systems/catering/api/member_catering.py` | 删除自助退 |
| `backend/app/systems/platform/manifest.py` | `payment:reconcile` 菜单 |
| `frontend/.../OrdersView.vue` 等 | 退款弹窗 + preview |
| `frontend/.../PaymentReconcileView.vue` | 对账台 |
| `member-web/src/api/pay.ts` | 真实模式轮询 query |
| `member-web/.../OrderDetailView.vue` | 去自助退 |
| `backend/tests/test_payment_refund_hardening.py` | 契约测试 |

---

### Task 1: 迁移与模型

**Files:**
- Create: `backend/alembic/versions/20260805_0015_payment_refund_hardening.py`
- Modify: `backend/app/systems/platform/models/commerce.py`
- Modify: `backend/app/systems/platform/models/payment_settings.py`
- Modify: `backend/app/models/__init__.py`

**Interfaces:**
- Produces: `Order.refunded_amount: Decimal`；`RefundIntent` 模型；`PaymentIntent.status` 含 `closed|failed`

- [x] **Step 1:** 迁移 `orders.refunded_amount` 默认 0；建表 `refund_intents`（字段对齐规格 §3.3，含 `suggested_amount`、`force`）
- [x] **Step 2:** ORM 同步；导出模型
- [x] **Step 3:** `Base.metadata.create_all` 测试夹具下可建表（跑任意现有 pytest 冒烟）

---

### Task 2: 支付回调防伪 + 查单（P1）

**Files:**
- Modify: `backend/app/systems/platform/services/wechat_pay.py`
- Modify: `backend/app/systems/platform/api/payment_notify.py`
- Modify: `backend/app/systems/platform/api/member_portal.py`（预下单关闭旧 intent；member query）
- Modify: `backend/app/systems/platform/api/commerce.py`（staff query）
- Modify: `member-web/src/api/pay.ts`
- Modify: `miniprogram/utils/pay.js`
- Test: `backend/tests/test_payment_refund_hardening.py`

**Interfaces:**
- Produces: `verify_and_decrypt_notify(headers, body, cfg) -> dict`；`query_wechat_order(cfg, out_trade_no) -> status`；`POST .../pay/query`

- [x] **Step 1:** 写失败测试：`dry_run=false` 时 POST 明文 `{"out_trade_no":...}` 不得把订单变 paid
- [x] **Step 2:** 实现：非 dry_run 必须验签+解密；金额校验；已 paid 幂等 ACK
- [x] **Step 3:** 预下单前将同订单 `created` intent 置 `closed`
- [x] **Step 4:** 管理端/会员 `pay/query`：dry_run 读本地；真实调微信；SUCCESS 则 fulfill
- [x] **Step 5:** H5/小程序：非 dry_run 轮询 query 后再提示成功
- [x] **Step 6:** pytest 相关用例通过

---

### Task 3: 退款 preview + 编排（P2）

**Files:**
- Create: `backend/app/systems/platform/services/refunds.py`
- Modify: `backend/app/systems/platform/services/wechat_pay.py`（退款/查退款）
- Modify: `backend/app/systems/platform/api/commerce.py`
- Modify: `backend/app/systems/platform/api/payment_notify.py`（refund-notify）
- Modify: `backend/app/systems/gym/services/fulfillment.py` 或 refunds 内调用作废/撤权
- Modify: `backend/app/systems/catering/api/member_catering.py`（删自助退）
- Modify: `frontend/src/systems/platform/views/OrdersView.vue`
- Modify: `frontend/src/systems/catering/views/CateringOrdersView.vue`
- Modify: `member-web/src/views/catering/OrderDetailView.vue`
- Test: `backend/tests/test_payment_refund_hardening.py`（扩展）

**Interfaces:**
- Produces: `preview_refund(db, order) -> dict`；`create_refund(..., amount, channel, force, reason, staff)`；成功回调 `apply_refund_success(intent)`

- [x] **Step 1:** 实现 preview：期限/次卡/储值/课包公式（规格 §5.2.1）；续卡按本单增量回退口径
- [x] **Step 2:** `POST /orders/{id}/refund`：渠道校验；会籍非 force 金额==suggested；写 refund_intent；dry_run 立即成功或 wechat 下单
- [x] **Step 3:** `apply_refund_success`：写 payments.refund（渠道正确）、累加 refunded_amount、会籍/课包终止权益、零售全额回补/部分不回补、券仅全额回退
- [x] **Step 4:** 退款回调验签解密幂等
- [x] **Step 5:** 删除会员餐饮 refund 路由与 H5 按钮
- [x] **Step 6:** 管理端退款弹窗调 preview；超管 force
- [x] **Step 7:** pytest：未使用全额、已使用比例、force 少退、零售部分退不回补、会员退 404

---

### Task 4: 对账补单台（P3）

**Files:**
- Create: `backend/app/systems/platform/api/payment_reconcile.py`
- Modify: `backend/app/systems/platform/manifest.py`
- Modify: `backend/app/main.py`
- Create: `frontend/src/systems/platform/views/PaymentReconcileView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: docs（PRD §10、user.md、旧微信规格非目标交叉引用）
- Test: 对账权限与强制补履约

**Interfaces:**
- Produces: `GET /site/payment-reconcile/items?kind=`；`POST .../actions/query-pay|close-intent|query-refund|mark-offline-refunded|force-fulfill|force-refund-success`

- [x] **Step 1:** 列表三类异常（规格 §6.2）；N=15 分钟可配置常量
- [x] **Step 2:** 行操作；force-* 仅超管 + 审计
- [x] **Step 3:** 权限 `payment:reconcile` + 菜单「支付对账」
- [x] **Step 4:** 前端对账页
- [x] **Step 5:** 文档回写；规格状态 → 已落地；全量 `pytest -q`

---

## Execution Handoff

Plan saved to `docs/superpowers/plans/2026-08-05-payment-refund-hardening.md`.

**执行方式二选一：**

1. **Subagent-Driven（推荐）** — 每任务新开子代理，任务间复核  
2. **Inline Execution** — 本会话按 executing-plans 连续推进  

选哪个？选后从 Task 1 开始实现。
