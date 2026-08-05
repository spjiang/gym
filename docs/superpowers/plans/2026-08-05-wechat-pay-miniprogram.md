# 微信支付 + 小程序完善 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans or implement task-by-task. Steps use checkbox (`- [ ]` / `- [x]`) syntax for tracking.

**Goal:** 场地级微信商户统一配置（管理端可配）；会员端小程序 JSAPI + H5（微信内 JSAPI / 站外 MWEB）预下单与回调履约；完善小程序主路径。

**Architecture:** `site_payment_settings` 落库（密钥加密）→ Provider 读库优先于 env → `payment_intents` 预下单 → 微信 APIv3 / DRY_RUN → notify 幂等履约；小程序/H5 绑定 openid 后调起支付。

**Tech Stack:** FastAPI · Alembic · httpx + cryptography（APIv3 签名）· Vue 管理端 · 原生微信小程序 · member-web

**Spec:** `docs/superpowers/specs/2026-08-05-wechat-pay-miniprogram-design.md`

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 全场地共用一套微信商户号；密钥永不在 GET 明文回显
- 会员端支付：预下单后待回调（或 dry-run confirm）；管理端代收可保持即时成功
- 未要求不 git commit
- 验证：pytest + DRY_RUN 冒烟

## File Map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/20260805_0014_wechat_payment.py` | settings / bindings / intents |
| `backend/app/systems/platform/models/payment_settings.py` | 模型 |
| `backend/app/core/crypto_secrets.py` | Fernet 加解密 |
| `backend/app/systems/platform/services/payment_settings.py` | 读有效配置 |
| `backend/app/systems/platform/services/payments.py` | Provider 改造 |
| `backend/app/systems/platform/services/wechat_pay.py` | APIv3 下单/验签 |
| `backend/app/systems/platform/api/payment_settings.py` | 管理端配置 API |
| `backend/app/systems/platform/api/payment_notify.py` | 回调 + dry-run confirm |
| `backend/app/systems/platform/api/member_auth.py` | openid bind |
| `backend/app/systems/platform/api/member_portal.py` | 预下单响应 |
| `backend/app/systems/platform/manifest.py` | 菜单/权限 |
| `frontend/.../PaymentSettingsView.vue` | 配置页 |
| `miniprogram/**` | 选店/支付/对齐主路径 |
| `member-web` 支付工具 | 双场景 |
| `backend/tests/test_wechat_payment.py` | 契约测试 |

---

### Task 1: 迁移 + 加密 + 配置读写

- [x] **Step 1:** 表 `site_payment_settings`、`member_wechat_bindings`、`payment_intents`
- [x] **Step 2:** `crypto_secrets` + `resolve_payment_settings(site_id)`
- [x] **Step 3:** `GET/PUT/import-env` API + 权限 `payment:config` + manifest 菜单
- [x] **Step 4:** 管理端 `PaymentSettingsView` + 路由
- [x] **Step 5:** pytest 配置脱敏与落库优先

### Task 2: 预下单 + 回调 + DRY_RUN

- [x] **Step 1:** Wechat APIv3 客户端（dry_run 短路）
- [x] **Step 2:** 会员 `pay/online` 返回 `jsapi_params`/`mweb_url`，不立即 paid
- [x] **Step 3:** `notify` + `pay/dry-run-confirm` 履约
- [x] **Step 4:** 管理端 `pay/online` 保持即时成功（mock/dry_run）
- [x] **Step 5:** pytest 全流程

### Task 3: openid 绑定 + 小程序

- [x] **Step 1:** `mini/bind`、`oa/bind`（code 换 openid；dry 配置下用 mock openid）
- [x] **Step 2:** 小程序：选店、支付调起、清吧/会籍等主路径
- [x] **Step 3:** README 联调说明

### Task 4: H5 双场景支付

- [x] **Step 1:** `payScene` 检测 + OAuth bind 入口（可先 mock code）
- [x] **Step 2:** 订单支付页/流程接新响应
- [x] **Step 3:** 文档 / PRD §10 / user.md；规格状态 → 已落地

## Execution Handoff

Plan saved. Implement Task 1→4 sequentially; skip commits unless asked.
