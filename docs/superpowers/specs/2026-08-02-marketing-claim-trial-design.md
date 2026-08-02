# 营销增强：会员领券 + 体验卡

日期：2026-08-02  
状态：已批准（方案 A）  
对应 change：`marketing-claim-trial-ops`（待创建）

## 背景

一期营销 Web 优惠券闭环已交付。PRD §5.5 / §6.2 仍缺会员端领券与体验卡。活动价/限时价不在本刀。

## 目标

1. 会员可在 H5 查看可领券并自助领取（含每人限领与发放上限）。
2. 会籍卡种可标记为体验卡，走现有购卡/履约/门禁链路。

## 设计

### 领券

- `CouponTemplate` 增加：`claimable: bool`（默认 false）、`per_member_limit: int`（默认 1）。
- 员工创建模板时可配置；员工 `/coupons/issue` 保留。
- 会员 API：
  - `GET /member/coupons/claimable?merchant_id=` — 可领模板列表
  - `POST /member/coupons/claim` — `{ merchant_id?, template_id }`
  - `GET /member/coupons` — 本人持券
- 领取校验：模板启用且 `claimable`、在有效期内、未达 `total_limit`、该会员未达 `per_member_limit`。
- H5：商城或独立入口展示可领券并领取。

### 体验卡

- `MembershipProduct` 增加：`is_trial: bool`（默认 false）。
- 后台卡种创建/列表展示体验标记；H5 目录返回并标注「体验」。
- 购卡、支付、履约、门禁与普通卡种相同；短期限/次卡由既有 `duration_days` / `session_count` 表达。
- 不做体验专属核销规则、不做临访自动转体验。

### 非目标

- 活动价/限时价、裂变分销、活动码、真短信推券。

## 验收

- 领取成功；重复超限拒绝；停用/不可领拒绝。
- 体验卡购买支付后生成会籍并可查询 `is_trial` 卡种。
- pytest 全绿；归档后回写 PRD §10。
