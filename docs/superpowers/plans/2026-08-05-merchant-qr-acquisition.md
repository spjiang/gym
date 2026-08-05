# 商户二维码获客与会员来源 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** 商户可出 H5 获客码；用户扫码 OTP 登录时自动注册并挂靠；主档记录首次来源（商户 / 综合运营平台）。

**Architecture:** `members` 增加 `acquisition_source` + `first_merchant_id`；OTP send/verify 支持未知手机号注册，verify 可选 `merchant_id` 挂靠；管理端商户页生成 `{MEMBER_WEB_PUBLIC_URL}/login?merchant_id=` 二维码；H5 登录页带参。

**Tech Stack:** FastAPI · Alembic · Vue 3 · qrcode · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-05-merchant-qr-acquisition-design.md`

**Next plan after this:** `docs/superpowers/plans/2026-08-05-admin-list-conventions.md`

## Global Constraints

- 交流与代码注释中文；禁止过时 API
- 首次来源只在**新建会员**时写入，之后挂店不改
- OTP 仍走 `MEMBER_OTP_*`；mock 码默认 `123456`
- 未要求不 git commit（步骤中的 commit 可跳过）
- 验证：pytest + 扫码链接手工冒烟

## File Map

| 路径 | 职责 |
|------|------|
| `backend/alembic/versions/20260805_0013_member_acquisition.py` | 来源字段 + OTP `member_id` 可空 |
| `backend/app/systems/platform/models/member.py` | Member 字段 |
| `backend/app/systems/platform/models/otp.py` | `member_id` nullable |
| `backend/app/systems/platform/services/otp.py` | 按 phone 发码/校验 |
| `backend/app/systems/platform/api/member_auth.py` | 注册登录 + merchant_id |
| `backend/app/core/schemas/common.py` | `MemberOut` 来源字段 |
| `backend/app/systems/platform/api/members.py` | 列表带来源名 |
| `backend/app/systems/platform/api/member_portal.py` | `/me` 带来源 |
| `backend/app/core/config.py` + `.env.example` | `MEMBER_WEB_PUBLIC_URL` |
| `backend/app/systems/platform/api/org.py` | 商户获客链接 |
| `backend/tests/test_member_acquisition.py` | 获客闭环测试 |
| `member-web/src/views/LoginView.vue` | `merchant_id` query |
| `frontend/src/systems/platform/views/MerchantsView.vue` | 二维码弹层 |
| `user.md` / README | 验收说明 |

---

### Task 1: 迁移 + 模型

**Files:**
- Create: `backend/alembic/versions/20260805_0013_member_acquisition.py`（`down_revision = "20260804_0012"`）
- Modify: `backend/app/systems/platform/models/member.py`
- Modify: `backend/app/systems/platform/models/otp.py`

- [x] **Step 1: Member 模型增加枚举与字段**

```python
class AcquisitionSource(str, Enum):
    MERCHANT = "merchant"
    PLATFORM = "platform"

# Member 内
acquisition_source: Mapped[str] = mapped_column(
    String(32), default=AcquisitionSource.PLATFORM.value, nullable=False
)
first_merchant_id: Mapped[int | None] = mapped_column(
    ForeignKey("merchants.id"), nullable=True, index=True
)
```

- [x] **Step 2: OTP `member_id` 改为可空**

```python
member_id: Mapped[int | None] = mapped_column(ForeignKey("members.id"), nullable=True, index=True)
```

- [x] **Step 3: Alembic upgrade** — 加列、`member_otp_challenges.member_id` nullable、Postgres 回填最早挂靠为首次来源

- [x] **Step 4: 启动 backend 确认 revision `20260805_0013`**

---

### Task 2: OTP 按手机号 + 注册登录 API

**Files:**
- Modify: `backend/app/systems/platform/services/otp.py`
- Modify: `backend/app/systems/platform/api/member_auth.py`
- Create: `backend/tests/test_member_acquisition.py`

**Interfaces:**
- `send_member_otp(db, *, phone: str, member_id: int | None = None) -> str`
- `verify_member_otp(db, *, phone: str, code: str) -> None`（按 phone；mock 无挑战可比对 mock 码）
- `OtpSendIn` / `OtpVerifyIn` 增加 `merchant_id: int | None = None`
- 新用户：`site_id` 取 `Site` 最小 id；`name=f"会员{phone[-4:]}"`；写来源；可选 `MerchantMember`

- [x] **Step 1: otp 服务改为 phone 主查询，允许 `member_id=None` 写挑战**

- [x] **Step 2: `send_otp` 取消「会员不存在」404；`verify_otp` 实现注册/挂靠/发 token（见规格 §3.1）**

- [x] **Step 3: 写并跑 `tests/test_member_acquisition.py`**

```bash
docker compose run --no-deps --rm -e PYTHONPATH=/app \
  -v "$PWD/backend/tests:/app/tests" -w /app backend \
  pytest tests/test_member_acquisition.py -q
```

Expected: 新号+店 → `merchant` 来源；同号第二店 → 双挂靠且 `first_merchant_id` 不变；无店 → `platform`

---

### Task 3: MemberOut /me / 管理端带来源

**Files:**
- Modify: `backend/app/core/schemas/common.py`
- Modify: `backend/app/systems/platform/api/members.py`
- Modify: `backend/app/systems/platform/api/member_portal.py`

- [x] **Step 1: Out 增加 `acquisition_source`、`first_merchant_id`、`first_merchant_name`**

- [x] **Step 2: `_member_out` 与 `member_me` 填充商户名**

- [x] **Step 3: 测试断言字段存在**

---

### Task 4: MEMBER_WEB_PUBLIC_URL + 获客链接 API

**Files:**
- Modify: `backend/app/core/config.py`、`.env.example`
- Modify: `backend/app/systems/platform/api/org.py`

- [x] **Step 1: `member_web_public_url` 默认 `http://localhost:8081`**

- [x] **Step 2: `GET /merchants/{id}/acquisition-link` → `{ merchant_id, url }`，需 `org:read` 且可访问该商户**

---

### Task 5: 管理端二维码弹层

**Files:**
- Modify: `frontend/package.json`（加 `qrcode`）
- Modify: `frontend/src/systems/platform/views/MerchantsView.vue`

- [x] **Step 1: 商户行增加「获客码」→ 拉 acquisition-link → QR + 复制 + 下载**

- [x] **Step 2: `docker compose up --build -d frontend` 冒烟**

---

### Task 6: H5 登录带参 + 文档

**Files:**
- Modify: `member-web/src/views/LoginView.vue`
- Modify: `user.md`、`README.md`
- Modify: spec 状态 → 已落地

- [x] **Step 1: `merchant_id` 传入 send/verify；成功后优先进该店业态首页**

- [x] **Step 2: 重建 member-web；`/login?merchant_id=1` + 新号冒烟**

- [x] **Step 3: 文档补充获客码与「综合运营平台」来源说明**

---

## Spec coverage

| Spec | Task |
|------|------|
| 字段+迁移 | 1 |
| OTP 注册挂靠 | 2 |
| 展示字段 | 3 |
| 出码 URL/API | 4 |
| 管理端 QR | 5 |
| H5 带参 | 6 |

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-05-merchant-qr-acquisition.md`.
