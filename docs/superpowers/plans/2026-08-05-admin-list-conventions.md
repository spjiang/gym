# 管理端列表规范 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 管理端主要列表统一检索、服务端分页、详情/编辑入口；关联会员时展示用户信息与首次来源。

**Architecture:** 共享 `PageIn` / `PageOut`；先会员+订单（A1）作范式，再健身房 → 餐饮 → 平台其余分批。

**Tech Stack:** FastAPI · Vue 3 · Element Plus

**Spec:** `docs/superpowers/specs/2026-08-05-admin-list-conventions-design.md`

**Depends on:** `docs/superpowers/plans/2026-08-05-merchant-qr-acquisition.md` 已完成（来源字段可用）

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 大数据表禁止前端假分页；目录型小表可标「全量例外」
- 未要求不 git commit
- 分批交付，每批可独立验收

## File Map（A1）

| 路径 | 职责 |
|------|------|
| `backend/app/core/schemas/paging.py` | `PageIn` / `PageOut` |
| `backend/app/systems/platform/api/members.py` | 会员分页检索 |
| 订单 list 所在 API 模块 | 订单分页 + member 嵌套 |
| `frontend/src/systems/platform/views/MembersView.vue` | 检索/分页/详情 |
| `frontend/src/systems/platform/views/OrdersView.vue` | 同上 |
| `backend/tests/test_admin_list_paging.py` | 分页契约 |

---

### Task A1-1: 分页 Schema + 会员列表

**Files:**
- Create: `backend/app/core/schemas/paging.py`
- Modify: `backend/app/systems/platform/api/members.py`
- Modify: `frontend/src/systems/platform/views/MembersView.vue`
- Test: `backend/tests/test_admin_list_paging.py`

**Interfaces:**

```python
class PageIn(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

class PageOut(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
```

`GET /members?page=&page_size=&q=` → `PageOut[MemberOut]`（前后端同发，直接改契约）。

- [x] **Step 1: 实现 `paging.py` 与会员分页（关键词匹配 phone/name）**

- [x] **Step 2: MembersView — 检索区、分页、详情抽屉（含来源文案）、编辑（有 `member:write` 时）**

- [x] **Step 3: pytest + 手工冒烟**

---

### Task A1-2: 订单列表范式

**Files:**
- Modify: 订单 list API（现网 `commerce` / orders 路由）
- Modify: `frontend/src/systems/platform/views/OrdersView.vue`

- [x] **Step 1: 订单分页 + 状态/商户/`q`；行内 `member: { id, name, phone } | null`**

- [x] **Step 2: 前端检索、分页、详情抽屉（含用户信息）**

- [x] **Step 3: 冒烟**

---

### Task A2: 健身房相关列表

**Files:** 会籍实例、门禁事件等对应 API + View

- [x] **Step 1: 按 A1 契约改造会籍列表（含会员列）**
- [x] **Step 2: 门禁事件列表分页 + 会员信息**
- [x] **Step 3: 冒烟并勾选规格验收项**

**全量例外（本批可保留）：** 会籍卡种目录若数据量小，可暂全量 + 前端筛选，在 PR 注明。

---

### Task A3: 团课 / 零售 / 券 / 器材

- [x] **Step 1: 预约/课包等挂会员的列表分页 + 用户列**
- [x] **Step 2: 零售流水分页**
- [x] **Step 3: 冒烟**

**全量例外：** 零售分类、券模板目录等。

---

### Task A4: 餐饮 + 平台其余

- [x] **Step 1: 餐饮订单分页 + 用户列（若有 member_id）**
- [x] **Step 2: 员工/通知等列表检索分页**
- [x] **Step 3: 更新 PRD §10；规格状态 → 已落地（批次说明写清）**

---

## Spec coverage

| Spec | Task |
|------|------|
| 骨架/检索/分页 | A1–A4 |
| 用户列+来源 | A1-1（依赖获客） |
| 详情/编辑 | A1-1, A1-2 |
| 分批 | A2–A4 |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-05-admin-list-conventions.md`.


## 全量目录例外清单

以下小表暂保留全量拉取（或 `page_size=100` 上限拉取），不强制服务端关键词分页：

- 会籍卡种、私教课包商品、团课课程/场次目录
- 零售分类 / SKU 目录、优惠券模板
- 商户类型、门禁点/设备、角色/权限定义菜单
