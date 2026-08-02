## Context

底座已归档：会员、门禁、订单支付骨架可用。本 change 在健身房商户上增加会籍业态，见 `proposal.md`。行为契约见本目录 `specs/*`。

## Goals / Non-Goals

**Goals:**

- 卡种可配置；办卡/续卡经订单支付履约
- 会籍状态可管理；与门禁授权联动
- 管理后台可操作；测试覆盖主路径

**Non-Goals:**

- 小程序购卡 UI、真实微信进件、课程校验以外的业态

## Decisions

### 1. 领域落在 `backend/app` 的 `membership` 包

- 表：`membership_products`（卡种）、`memberships`（会籍实例）、可选 `membership_events`
- 卡种 `product_type`: `term` | `count` | `value`
- 默认门禁策略：**卡种必须绑定至少 1 个门禁点，否则不可办卡**（写死，避免隐式全开）

### 2. 履约钩子挂在支付成功路径

- `pay_offline` / `pay_online` 成功后，若 `order_type == membership`，调用 `MembershipFulfillmentService`
- 办卡订单 payload 存 `member_id` + `product_id`（可用 order 扩展字段或旁路关联表 `membership_order_links`）
- 推荐：`membership_orders` 关联表（order_id, member_id, product_id, action=purchase|renew, target_membership_id?）

### 3. 续卡规则（一期写死）

- 期限卡：若当前仍有效，从 `max(now, current_end)` 起加天数；若已过期，从 now 起加天数
- 次卡/储值：在原会籍上增加次数/余额；若无有效实例则新建

### 4. 停卡与授权

- 停卡 → 会籍 `frozen` + 撤销关联 AccessGrant + 异步同步
- 复卡（可选一期）：恢复状态并重建授权；若工期紧可二期，任务中标注

### 5. 前端

- 页面：卡种管理、会籍列表、会员详情内「办卡/续卡」对话框
- 权限：`membership:manage` / `membership:sell`；商户管理员与前台可售，教练只读（若需）

## Risks / Trade-offs

- [支付成功但履约失败] → 订单保持已支付，履约状态字段/重试任务，禁止假装未收款  
- [门禁点变更后旧会籍] → 一期不自动迁移；新办按新卡种绑定  
- [时区] → 统一 UTC 存储，展示用场地本地时区（配置已有可先 UTC）

## Migration Plan

- Alembic 新增 membership 相关表与权限点种子  
- 回滚：开发环境可降级迁移  

## Open Questions

- 储值卡扣费业务（馆内消费）留待零售切片；本 change 仅支持办卡充值入账余额字段
