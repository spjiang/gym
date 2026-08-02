# 私教与团课（Web 后台）Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 Web 后台交付教练档案、私教课包售卖/核销、团课排课/代约/签到，满员不可约，约课需本商户生效会籍。

**Architecture:** 新增 `backend/app/models/course.py` 与 `api/course.py`；私教履约挂在支付成功钩子（`order_type=pt_package`），模式对齐会籍 `fulfillment.py`；团课预约用事务 + 场次行锁防超卖。前端新增教练/课包/团课/教练工作台页面，权限点写入 seed。

**Tech Stack:** FastAPI · SQLAlchemy 2 · Alembic · pytest · Vue 3 · Pinia · Element Plus · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-02-pt-group-class-design.md`  
**建议 OpenSpec change:** `pt-group-class-ops`

## Global Constraints

- 代码注释使用中文；禁止过时 API
- 仅 Web 后台；不做小程序约课
- 满员不可约；取消释放名额；无候补
- 约团课须本商户生效会籍（`Membership.status == active` 且未过期）
- 团课签到不扣会籍次卡次数
- 私教核销默认扣 1 课时
- 支付继续线下登记 + mock 线上；履约失败可追踪
- 商户数据隔离；教练仅本人数据
- 完成后更新 PRD §10 交付对照表

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/models/course.py` | Coach / Pt* / Group* 模型 |
| `backend/alembic/versions/20260802_0003_course.py` | 迁移 |
| `backend/app/services/pt_fulfillment.py` | 私教课包履约 |
| `backend/app/services/course_booking.py` | 预约/取消/满员/会籍校验 |
| `backend/app/api/course.py` | HTTP API |
| `backend/app/main.py` | 挂载 router |
| `backend/app/seed.py` | 权限点 |
| `backend/app/api/commerce.py` 或支付成功处 | 调用 pt 履约 |
| `backend/tests/test_course_ops.py` | 主路径测试 |
| `frontend/src/views/CoachesView.vue` 等 | 后台页 |
| `frontend/src/router/index.ts` · `LayoutView.vue` | 路由与菜单 |
| PRD §10 | 进度回写（archive 后） |

---

### Task 1: 模型与迁移

**Files:**
- Create: `backend/app/models/course.py`
- Create: `backend/alembic/versions/20260802_0003_course.py`
- Modify: `backend/app/models/__init__.py`（导出新模型）

**Interfaces:**
- Produces: 表 `coaches`, `pt_package_products`, `pt_package_product_coaches`, `pt_packages`, `pt_order_links`, `group_courses`, `group_sessions`, `group_bookings`

- [ ] **Step 1: 定义模型**（字段对齐设计 §3；`GroupBooking` 对 `(session_id, member_id)` 唯一且仅对非 cancelled 用部分唯一或应用层校验 + 事务）

枚举建议：`PtPackageStatus`: active|exhausted|expired|void；`GroupSessionStatus`: open|cancelled；`GroupBookingStatus`: booked|cancelled|attended|no_show。

- [ ] **Step 2: 编写 Alembic `20260802_0003_course.py` 并 `alembic upgrade head`（或测试库建表）**

- [ ] **Step 3: 确认模型可 import**

Run: `cd backend && python -c "from app.models.course import Coach, PtPackage, GroupSession, GroupBooking; print('ok')"`  
Expected: `ok`

---

### Task 2: 权限种子

**Files:**
- Modify: `backend/app/seed.py`

**Interfaces:**
- Produces: 权限 `coach:manage`, `course:manage`, `course:book`, `course:checkin`, `pt:sell` 写入商户管理员/前台/教练角色（教练含 `course:checkin` + 只读所需）

- [ ] **Step 1: 扩展 `ROLE_DEFINITIONS` 权限列表并保证 seed 幂等合并**

- [ ] **Step 2: 本地跑 seed 或依赖测试 fixture 验证角色含新权限**

---

### Task 3: 私教履约服务 + 支付钩子

**Files:**
- Create: `backend/app/services/pt_fulfillment.py`
- Modify: 支付成功路径（查找 `fulfill_membership_order` / `pay_offline` 同类调用点并并列调用）

**Interfaces:**
- Produces: `fulfill_pt_package_order(db, order: Order) -> PtPackage | None`
- Consumes: `PtOrderLink(order_id, member_id, product_id)`, `PtPackageProduct`

- [ ] **Step 1: 写失败测试** `test_pay_offline_fulfills_pt_package`

```python
def test_pay_offline_fulfills_pt_package(client, admin_headers, gym_merchant, member):
    # 创建课包商品 → purchase → pay_offline → 列表可见 active 课包且 remaining_sessions 正确
    ...
```

- [ ] **Step 2: 实现 `purchase` 下单建 `PtOrderLink` + `fulfill_pt_package_order`（starts_at=now, ends_at=now+valid_days, remaining=session_count）**

- [ ] **Step 3: 支付成功分支：`if order.order_type == "pt_package": fulfill_pt_package_order(...)`，失败写入 `fulfill_error`，不回滚支付状态**

- [ ] **Step 4: pytest 通过**

---

### Task 4: 私教核销 API

**Files:**
- Create/Modify: `backend/app/api/course.py`（`POST /pt-packages/{id}/consume`）
- Modify: `backend/app/main.py` include router
- Test: `backend/tests/test_course_ops.py`

**Interfaces:**
- Produces: `consume_pt_session(db, package_id, actor) -> PtPackage`；剩余 −1；至 0 则 `exhausted`；过期/作废/无课时 → 400

- [ ] **Step 1: 测试核销成功与课时不足拒绝**

- [ ] **Step 2: 实现 consume + 审计 `pt.consume`**

- [ ] **Step 3: pytest 通过**

---

### Task 5: 教练与课包商品 CRUD API

**Files:**
- Modify: `backend/app/api/course.py`
- Test: `backend/tests/test_course_ops.py`

**Interfaces:**
- `GET/POST/PATCH /coaches`，`POST /coaches/{id}/deactivate`
- `GET/POST/PATCH /pt-products`，停用接口；适用教练通过 body `coach_ids: list[int] | null`（null=全部教练）

- [ ] **Step 1: 测试创建教练（绑定 staff_user_id）与课包商品**

- [ ] **Step 2: 实现 CRUD + `coach:manage` / `course:manage` / `pt:sell` 鉴权**

- [ ] **Step 3: pytest 通过**

---

### Task 6: 团课课程、场次、代约/取消（含满员与会籍）

**Files:**
- Create: `backend/app/services/course_booking.py`
- Modify: `backend/app/api/course.py`
- Test: `backend/tests/test_course_ops.py`

**Interfaces:**
- `has_active_membership(db, merchant_id, member_id) -> bool`
- `book_group_session(db, session_id, member_id, *, force_cancel_window=False) -> GroupBooking`
- `cancel_group_booking(db, booking_id, *, force=False) -> GroupBooking`

规则：
1. `SELECT ... FOR UPDATE` 锁住 `group_sessions` 行  
2. 统计 `status == booked` 数量；`>= capacity` → `AppError("session_full", ...)`  
3. 无生效会籍 → `AppError("membership_required", ...)`  
4. 已存在 booked → 冲突拒绝  
5. 取消：`booked → cancelled`；管理员/前台可 `force` 忽略取消时限  

- [ ] **Step 1: 测试——有会籍可约、无会籍拒绝、满员拒绝、取消后可再约**

- [ ] **Step 2: 实现 `group-courses` / `group-sessions`（含改派 coach）/ `group-bookings`**

- [ ] **Step 3: pytest 通过**

---

### Task 7: 团课签到 + 教练数据范围

**Files:**
- Modify: `backend/app/api/course.py`
- Test: `backend/tests/test_course_ops.py`

**Interfaces:**
- `POST /group-bookings/{id}/checkin` body `{status: attended|no_show}`
- 列表场次/课包时：若角色为教练且无 manage，则 `coach.staff_user_id == current_user.id` 过滤

- [ ] **Step 1: 测试签到与教练只能看本人场次**

- [ ] **Step 2: 实现 checkin + 范围过滤 + 审计**

- [ ] **Step 3: pytest 通过**

---

### Task 8: 前端页面与菜单

**Files:**
- Create: `frontend/src/views/CoachesView.vue`
- Create: `frontend/src/views/PtPackagesView.vue`
- Create: `frontend/src/views/GroupCoursesView.vue`
- Create: `frontend/src/views/CoachDeskView.vue`
- Modify: `frontend/src/router/index.ts`
- Modify: `frontend/src/views/LayoutView.vue`

**Interfaces:**
- 调用 Task 5–7 的 REST；风格对齐 `MembershipsView.vue` / `ProductsView.vue`

- [ ] **Step 1: 路由与侧栏增加：教练、私教课包、团课、教练工作台**

- [ ] **Step 2: 实现列表/表单：售课（下单+引导去订单支付）、代约、取消、签到、核销**

- [ ] **Step 3: 手动或 smoke：管理员可完成售课→支付→核销；代约满员提示**

---

### Task 9: 回归、冒烟与文档

**Files:**
- Modify: `scripts/smoke_e2e.py`（可选追加课程路径）
- Modify: `docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` §10（**archive 后**再改）
- Modify: `docs/superpowers/specs/2026-08-02-pt-group-class-design.md` 状态 → 已批准

- [ ] **Step 1: `cd backend && pytest -q` 全绿**

- [ ] **Step 2: 冒烟脚本或手工验收设计 §6 清单**

- [ ] **Step 3: OpenSpec archive 后回写 PRD §10「私教/团课」为 ✅**

---

## Spec coverage self-check

| 规格项 | Task |
|--------|------|
| 教练档案 | 1, 5, 8 |
| 私教售卖履约 | 3, 8 |
| 私教核销 | 4, 8 |
| 团课模板/场次/代课 | 6, 8 |
| 满员不可约 / 会籍资格 | 6 |
| 签到不扣次卡 | 7 |
| 教练本人数据 | 7, 8 |
| 审计 | 3–7 |
| 不做小程序/候补/真微信 | 全局约束 |

## Placeholder scan

无 TBD；接口名与枚举在 Task 1/3/6 已固定。
