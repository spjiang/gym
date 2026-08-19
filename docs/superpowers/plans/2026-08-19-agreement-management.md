# 会员购买协议管理 Implementation Plan

> **For agentic workers:** 本会话内联执行。未要求 git commit。

**Goal:** 后台基础配置维护按商户+场景的购买协议；H5 / 小程序购买前勾选阅读；未启用协议则会员不能下单。

**Architecture:** `legal_agreements` 一商户一场景一行。后台 CRUD + 会员 GET。会籍 / 私教 / 活动报名 / 餐饮 checkout 在创建前调用 `require_enabled_agreement`。管理端 POS 不校验。

**Tech Stack:** FastAPI · Alembic · Vue 3 · 微信小程序 · pytest（compose 内 SQLite）

**Spec:** `docs/superpowers/specs/2026-08-19-agreement-management-design.md`

## Global Constraints

- 注释与交流中文；禁止过时 API
- 场景仅 `membership` / `pt_package` / `activity` / `dining`
- 无协议版本表、无签署落库、无 7 秒倒计时、无零售场景
- 验证：compose 内全量 pytest；frontend / member-web 需 `--build`

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/systems/platform/models/agreement.py` | 模型 |
| `backend/alembic/versions/20260819_0035_legal_agreements.py` | 迁移 |
| `backend/app/systems/platform/services/agreements.py` | 场景常量、require、sanitize |
| `backend/app/systems/platform/api/agreements.py` | 后台 CRUD |
| `backend/app/systems/platform/api/member_portal.py` | 会员 GET；购卡/课包校验 |
| `backend/app/systems/gym/api/member_activity.py` | 报名校验 |
| `backend/app/systems/catering/api/member_catering.py` | checkout 校验 |
| `backend/tests/test_agreements.py` | 新行为 |
| `frontend/.../AgreementsView.vue` | 基础配置页 |
| `member-web` 购买弹窗 | 勾选 + 全文 |
| `miniprogram` 购卡/报名/结算 | 同上 |

---

### Task 1: 模型 + 后台/会员 API + 下单拦截

- [ ] 红测 `test_agreements.py`
- [ ] 绿：模型、服务、后台 API、会员 GET、四处下单校验
- [ ] 更新已有会员购买测试先写入启用协议

### Task 2: 管理端协议管理页

- [ ] manifest / 路由 / 分组 / AgreementsView（textarea 正文，不做新编辑器依赖）

### Task 3: H5 + 小程序勾选

- [ ] 会籍/私教弹窗；活动报名；餐饮结算
- [ ] 小程序首页/商城/活动/餐饮结算
- [ ] 全量 pytest + `--build frontend member-web`
