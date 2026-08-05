# 支付安全加固 + 微信原路退 + 权益回滚 + 对账补单台 — 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-05 |
| 状态 | 已落地（P1–P3） |
| 关联 | PRD §4.5；`2026-08-05-wechat-pay-miniprogram-design`（支付配置/预下单已落地）；`commerce-skeleton` |
| 方案 | **方案 3**：统一支付/退款编排 + 对账/补单台 |
| 范围 | 支付回调防伪与查单确认；退款 intents 与微信原路/线下渠道；会籍课包权益回滚；零售餐饮部分退规则；管理端对账补单；移除会员餐饮自助退 |
| 非目标 | 多商户号分账；企业付款；按 SKU 行项目退货拣货；自动拉取微信账单文件做日终对账（可预留菜单入口，本期不做）；Native 扫码付 |

## 1. 背景与目标

上一切片已落地场地级微信配置与会员预下单，但审计发现：

- 支付回调可被明文 `out_trade_no` 伪造履约；无密文解密与验签。
- 退款仅为本地记账，不走微信原路；会籍/课包退款不回滚权益。
- 真实支付后前端易把「调起成功」当成「已支付」。
- 缺少运营侧查单、补履约、退款异常处理台。

本期把支付与退款做成**可上线收真钱、可退真钱、可对账补救**的闭环。

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 总体方案 | 方案 3（编排 + 对账补单台） |
| 会籍/课包退款 | **业界常见：未使用全额；已使用按剩余价值退，并终止剩余权益**（见 §5.2） |
| 会籍/课包金额 | 非 `force` 时退款金额**必须等于**系统计算的 `suggested_amount`；`force` 可在 `(0, 订单可退余额]` 内特批（可少退作违约金） |
| 零售/餐饮退款 | 支持任意部分退（≤ 可退余额）；与会籍计价无关 |
| 餐饮会员自助退 | **取消**；一律管理端 |
| 线下收款单退款 | 同一入口，强制选择 `offline_cash` / `offline_transfer` 并填原因 |
| 线上收款单退款 | 默认 `wechat_original` 原路退 |
| 零售部分退与库存 | **部分退不自动回补 SKU**；**全额退**仍整单回补 |

### 1.2 成功标准

- 非 `dry_run` 下无法用伪造 notify 将订单置为 `paid`。
- 会员真实支付后，须经回调或查单确认后才提示成功并完成履约。
- 线上支付全额/部分退款可走微信退款（DRY_RUN 可模拟成功）；线下单退款正确记渠道。
- 会籍/课包：预览给出 `suggested_amount`；退款成功后**剩余权益终止**并撤门禁；`force` 特批金额必审计。
- 对账台可处理：支付超时未回调、intent 与订单不一致、退款卡住；超管可人工补履约/补退结果（强审计）。
- 会员端餐饮不再提供自助退款。

## 2. 架构

```text
会员/管理端
    │
    ▼
支付编排 (payments / wechat_pay)
    ├─ payment_intents 预下单 / 关闭旧单
    ├─ notify 验签解密 → fulfill
    └─ query 查单 → fulfill / close
    │
退款编排 (refunds)
    ├─ preview 计价（会籍/课包剩余价值）
    ├─ 规则校验（金额/渠道/force）
    ├─ refund_intents
    ├─ wechat refund | 线下登记
    └─ 成功后：payments.refund + 累计退款 + 终止权益/库存回滚
    │
对账补单台 (reconcile API + 管理端页)
    ├─ 异常列表
    ├─ 一键查单 / 查退款
    └─ 超管强制补履约 / 补退结果
```

复用现有：`site_payment_settings`、`fulfill_paid_order`、零售回补、券回退、会籍停卡/作废与门禁同步能力。

## 3. 数据模型

### 3.1 订单扩展

| 字段 | 说明 |
|------|------|
| `refunded_amount` | `Numeric(12,2)`，默认 0；累计已成功退款 |
| `status` | 保持 `pending` / `paid` / `refunded` / `cancelled`；**部分退后仍为 `paid`**，退满为 `refunded` |

可退余额：`amount - refunded_amount`。

### 3.2 `payment_intents` 补强

| 字段/行为 | 说明 |
|-----------|------|
| `status` | `created` \| `succeeded` \| `closed` \| `failed` |
| 同订单新预下单 | 将同 `order_id` 下仍为 `created` 的旧 intent 置 `closed` |
| `amount` | 与订单金额一致，回调必须校验 |

### 3.3 新表 `refund_intents`

| 字段 | 说明 |
|------|------|
| `id` | PK |
| `site_id` / `order_id` | FK |
| `out_refund_no` | 商户退款单号，唯一 |
| `out_trade_no` | 关联原支付 intent（线上原路时） |
| `amount` | 本笔退款金额 |
| `channel` | `wechat_original` \| `offline_cash` \| `offline_transfer` |
| `status` | `created` \| `processing` \| `succeeded` \| `failed` |
| `force` | bool，是否特批（可偏离 suggested） |
| `suggested_amount` | 下单时系统建议金额快照（审计用） |
| `reason` | 原因 |
| `provider_ref` | 微信 refund_id 等 |
| `error_message` | 失败摘要 |
| `created_at` / `succeeded_at` | |
| `actor_staff_id` | 操作人 |

### 3.4 `payments` 流水

- `kind=refund` 的 `channel` 必须与本笔退款渠道一致（禁止再写死 `offline_cash`）。
- `note` 含 `out_refund_no` / 原因摘要。

## 4. 支付加固

### 4.1 回调 `POST /api/v1/payments/wechat/notify`

1. 读取微信平台签名头（`Wechatpay-Signature` 等）；校验失败 → 不履约。  
2. 用 `api_v3_key` AEAD 解密 `resource`；得不到明文 → FAIL。  
3. 解析 `out_trade_no`、`trade_state`、`amount.total`（分）。  
4. `trade_state != SUCCESS` → ACK 但不履约。  
5. 金额（分）必须等于 intent/订单金额。  
6. `mark_intent_succeeded` + `fulfill_paid_order`（已 paid 幂等）。  

**明确禁止**：当 `dry_run=false` 时，不得接受仅含明文 `out_trade_no`、无有效签名的请求。  

**DRY_RUN**：允许受控测试入口（仅 `dry_run=true`）：现有 `pay/dry-run-confirm`，或带共享测试头的简化 notify；不得在生产配置下启用。

### 4.2 查单

- `POST /api/v1/orders/{id}/pay/query`（管理端，`order:write` 或 `payment:reconcile`）  
- `POST /api/v1/member/orders/{id}/pay/query`（会员本人）  

行为：按最新支付 intent 调微信查单（DRY_RUN 读本地 intent）；若已支付则履约；若已关闭/失败则关闭 intent，订单保持 `pending`。

### 4.3 会员端确认

真实模式（非 immediate_capture、非 dry_run）：

1. 调起 JSAPI / 跳转 MWEB 后，**不**直接展示「购买成功」。  
2. 轮询 `pay/query`（如 2s 间隔，最长约 30–60s）直到 `paid` 或超时。  
3. 超时：提示「支付结果确认中，请稍后在订单查看或联系前台」，并进入对账台可处理的「待回调」列表（超时阈值可配置，默认 15 分钟列入异常）。

DRY_RUN / mock：保持现有快速确认路径。

## 5. 退款编排

### 5.1 API

**预览（会籍/课包必用，其它类型也可调）**

`GET /api/v1/orders/{id}/refund/preview` →

```json
{
  "order_id": 1,
  "order_type": "membership",
  "order_amount": "199.00",
  "refunded_amount": "0.00",
  "refundable_balance": "199.00",
  "suggested_amount": "120.00",
  "unused": false,
  "basis": "term_remaining_days",
  "detail": { "total_days": 30, "remaining_days": 18, "consumed_hint": "已使用 12 天" },
  "entitlement_action": "void_remaining",
  "force_required_if_amount_differs": true
}
```

**发起退款**

`POST /api/v1/orders/{id}/refund`

```json
{
  "amount": "120.00",
  "channel": "wechat_original|offline_cash|offline_transfer",
  "reason": "客户取消",
  "force": false
}
```

权限：`order:write`；`force=true` 仅场地超管（或 `payment:refund_force`）。

通用校验：

| 规则 | 行为 |
|------|------|
| 订单须曾支付且可退余额 > 0 | 否则 400 |
| `amount` ∈ (0, 可退余额] | |
| `membership` / `pt_package` | 见 §5.2；非 force 时 `amount` 必须等于当前 `suggested_amount` |
| 零售 / 餐饮 | `amount` 可任意 ≤ 可退余额 |
| 原支付 online + 原路 | 须能关联成功支付 `out_trade_no` |
| 原支付 offline | 禁止 `wechat_original`；必须 cash/transfer |
| 餐饮会员自助 | **删除** `POST /member/catering/orders/{id}/refund`；前端去掉按钮 |

### 5.2 会籍 / 课包：建议退款额与权益处理

对齐业界常见「剩余价值结算 + 终止剩余权益」（本期**不**做自动扣违约金比例；少退请用 `force` 把 `amount` 调低并写明原因）。

#### 5.2.1 `suggested_amount` 计算（金额精确到分，向下取整）

以本订单实付 `order.amount` 为基数（已退过的会籍单：`suggested` 还须 ≤ 可退余额）。通过订单履约 link 找到对应会籍/课包。

| 产品 | 未使用时 | 已使用时 |
|------|----------|----------|
| 期限卡 | `suggested = order.amount` | `floor(order.amount * remaining_days / total_days)`；`total_days` 取卡种 `duration_days`；`remaining_days` 取 `max(0, ceil((ends_at - now) / 1d))`，且不超过 `total_days` |
| 次卡 | `suggested = order.amount` | `floor(order.amount * remaining_sessions / original_sessions)`；`original_sessions` 取办卡时卡种次数（或履约快照） |
| 储值卡 | `suggested = order.amount` | `min(可退余额, 当前 balance)`（按剩余储值退，不超过订单可退） |
| 私教课包 | `suggested = order.amount` | `floor(order.amount * remaining_sessions / purchased_sessions)` |

**未使用判定**（用于 preview 的 `unused` 与文案；**不再作为「能不能退」的硬门槛**——已使用也可退剩余）：

| 类型 | 未使用 |
|------|--------|
| 期限卡 | 会籍生效后无成功放行事件 |
| 次卡 | `remaining_sessions == original_sessions` |
| 储值 | `balance == 办卡储值` |
| 课包 | `remaining_sessions == purchased_sessions` |

**续卡订单**：回退本单增加的权益后再算价——期限卡从 `ends_at` 扣回本单 `duration_days` 再计剩余；次卡/储值/课包扣回本单增加量。若扣回后会籍已无有效剩余，则 `suggested` 按扣回前剩余价值公式，成功后作废。

**已过期 / 已作废 / 剩余为 0**：`suggested_amount = 0`，不可退（除非 `force` 且超管特批金额，仍须 ≤ 可退余额；用于极端客诉）。

#### 5.2.2 金额与 `force`

| 场景 | 规则 |
|------|------|
| 非 force | `amount` **必须等于** preview 的 `suggested_amount`（`suggested=0` 则拒绝） |
| force | `amount` ∈ (0, 可退余额]；可低于 suggested（视为扣手续费/违约金），可高于 suggested 但不得超过可退余额（客诉特批） |

#### 5.2.3 退款成功后的权益（会籍/课包）

任一笔**成功的**会籍/课包退款（不论 suggested 全额或剩余比例）：

1. **终止剩余权益**：会籍作废或置不可用；课包作废；`sync_grants(..., revoke=True)`。  
2. 不保留「退了一半钱还留半张卡」的状态，避免账权不一致（少退钱用 force 表达违约金，而不是留残卡）。  
3. 写审计：suggested、实退、force、会籍/课包 id。

> 说明：若未来要支持「退一部分钱、卡缩短续用」，需另开切片（按比例改 `ends_at` / `remaining_sessions`）。本期明确采用「结清剩余并终止」。

### 5.3 零售 / 餐饮回滚

| 类型 | 退满（`refunded_amount >= order.amount`） | 未退满 |
|------|------------------------------------------|--------|
| 零售库存 | 整单回补 | **不**自动回补 |
| 券 | 回退核销 | 不回退 |
| 餐饮 | 仅状态/金额 | 仅累计退款 |

### 5.4 微信退款与 DRY_RUN

- 真实：APIv3 退款下单；可同步返回成功或 `processing`，以退款回调/查退款为准置 `succeeded`。  
- DRY_RUN：创建 refund_intent 后可立即 succeeded，或提供 `POST .../refund/dry-run-confirm`（仅 dry_run）。  
- 退款回调：`POST /api/v1/payments/wechat/refund-notify`（验签解密，幂等）。

### 5.5 订单状态与流水

1. refund_intent → succeeded  
2. 增加 `payments` refund 行（渠道正确）  
3. `refunded_amount += amount`  
4. 会籍/课包：执行 §5.2.3 终止剩余权益  
5. 零售/餐饮：按 §5.3  
6. 若 `refunded_amount >= order.amount` → `status=refunded`；否则保持 `paid`

## 6. 对账补单台

### 6.1 权限与菜单

- 权限：`payment:reconcile`（场地超管默认具备；可授予运营）  
- 菜单：综合经营 →「支付对账」（如 `/platform/payment-reconcile`）

### 6.2 列表与筛选

| 视图 | 条件（示例） |
|------|----------------|
| 支付待确认 | intent=`created` 且创建时间 > N 分钟（默认 15）且订单仍 `pending` |
| 支付不一致 | intent=`succeeded` 但订单非 `paid`；或订单 `paid` 但无 `charge` 流水 |
| 退款异常 | refund_intent ∈ {`processing`,`failed`} 或长时间未成功 |

### 6.3 操作

| 操作 | 谁 | 行为 |
|------|-----|------|
| 查单并同步 | reconcile | 调支付查单；已支付则履约 |
| 关闭支付意图 | reconcile | intent → `closed`（确认用户未付） |
| 查退款并同步 | reconcile | 微信查退款；成功则走退款成功落账 |
| 标记线下已退 | reconcile | 仅 `offline_*` 或运营确认场景；置 succeeded 并落账 |
| 强制补履约 | 仅超管 | 订单仍 pending 时执行 `fulfill_paid_order`；强审计 |
| 强制补退结果 | 仅超管 | 将 refund_intent 置成功并执行回滚/累计；强审计 |

所有强制操作写 `audit_logs`，summary 含操作人、订单号、原因。

## 7. 前端改造要点

- 管理端退款弹窗：先调 `refund/preview`；会籍/课包默认填入 `suggested_amount` 并展示计算说明；非超管不可改金额；超管 force 可改。  
- 渠道、原因必填。  
- 餐饮订单页：保留管理端退款；会员 H5/小程序移除自助退。  
- 会员支付工具：真实模式轮询 query。  
- 新页：支付对账台（表格 + 行内操作）。

## 8. 测试要求

- 伪造 notify（无签名）在 `dry_run=false` 下不得履约。  
- DRY_RUN：预下单 → confirm → paid；退款 dry-run → 累计/退满。  
- 会籍未使用：suggested=全额，退款后作废权益。  
- 会籍已使用：suggested=剩余比例，非 force 改金额被拒；按 suggested 退成功后权益终止。  
- force 少退：成功、权益仍终止、审计含 suggested/实退。  
- 零售部分退 → 不回补库存；全额退 → 回补。  
- 会员餐饮 refund API → 404/410。  
- 对账：强制补履约仅超管可。

## 9. 分期

| 阶段 | 内容 |
|------|------|
| P1 | 回调验签解密、金额校验、intent 关闭旧单、查单 API、会员轮询 |
| P2 | `refunded_amount` + `refund_intents`、preview 计价、退款 API/微信退款、会籍课包终止权益、去自助退、管理端退款表单 |
| P3 | 对账补单台 API+页面、权限菜单、测试与 PRD/user 文档回写 |

## 10. 验收清单

- [ ] 非 dry-run 伪造回调无法入账  
- [ ] 真实支付路径经 query/notify 后才 paid + 履约  
- [ ] 线上原路退与线下渠道退行为符合 §5  
- [ ] 会籍/课包 preview 计价与「结清剩余并终止」符合 §5.2  
- [ ] force 特批金额可少退且必审计  
- [ ] 零售部分退库存策略符合 §1.1  
- [ ] 会员不可自助退餐饮  
- [ ] 对账台三类异常可处理  
- [ ] pytest 覆盖 §8 关键路径  

## 11. 文档回写

落地后：更新 PRD §10 交易与支付行；`user.md` 说明对账台与退款规则；修正 `2026-08-05-wechat-pay-miniprogram-design` 非目标中「原路退另开」为已由本规格承接。
