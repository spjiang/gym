# 商户二维码获客与会员来源 — 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-05 |
| 状态 | 已落地（2026-08-05） |
| 关联 | PRD §6.2；会员 H5 `member-web`；会员主档 `members` / `merchant_members`；商户管理 |
| 范围 | 会员来源字段、扫码 OTP 自动注册与挂靠、管理端商户二维码、H5 登录带参 |
| 非目标 | 微信开放平台原生扫码组件定制；小程序码；短链服务商；员工邀请码；改写已有会员的历史来源回填策略以外的营销归因 |
| 实现顺序 | **本规格优先于** `2026-08-05-admin-list-conventions-design.md` |

## 1. 背景与目标

会员可关联多个商户，但缺少「从哪进来」的记录；也没有按商户出码的自助获客路径。综合运营平台入口与扫店码入口需可区分。

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 首次来源落库 | **会员主档**记一份：`acquisition_source` + `first_merchant_id`；之后再挂店不改首次来源 |
| 扫码落地 | 会员 H5 `/login?merchant_id={id}` |
| 出码位置 | 管理端商户列表/详情「二维码」按钮（可下载/复制链接） |
| 无码登录 | 视为综合运营平台入口：`acquisition_source=platform`，`first_merchant_id` 为空 |
| 多店 | 已有主档再扫其它店码：仅新增 `MerchantMember`，不改主档首次来源 |

### 1.2 成功标准

- 每活跃商户可生成指向 H5 登录页的二维码与链接。
- 新用户扫店码 → OTP → 自动建档并挂靠该商户；主档记录首次商户。
- 老用户扫新店码 → 登录后挂靠该店；首次来源不变。
- 无 `merchant_id` 登录新建的会员，来源展示为「综合运营平台」。
- 管理端会员详情/列表可看出首次来源（商户名或平台）。

## 2. 数据模型

### 2.1 `members` 新增字段

| 字段 | 类型 | 说明 |
|------|------|------|
| `acquisition_source` | `varchar(32)` NOT NULL | `merchant` \| `platform`；默认迁移策略见 §2.3 |
| `first_merchant_id` | `int` NULL FK→`merchants.id` | 仅当 `acquisition_source=merchant` 时有值 |

约束建议：

- `acquisition_source=platform` ⇒ `first_merchant_id IS NULL`
- `acquisition_source=merchant` ⇒ `first_merchant_id IS NOT NULL`（应用层保证；历史脏数据迁移后校验）

### 2.2 `merchant_members`

保持现有唯一约束 `(merchant_id, member_id)`；本切片**不强制**增加「本次扫码来源」列（主档已够表达首次来源）。

### 2.3 已有数据迁移

- 已有 `MerchantMember` 的会员：`acquisition_source=merchant`，`first_merchant_id=` 其**最早**一条挂靠的 `merchant_id`。
- 无任何挂靠的会员：`acquisition_source=platform`，`first_merchant_id=NULL`。

## 3. 登录与挂靠流程

```
GET /login?merchant_id=N（可选）
  → 本地暂存 pendingMerchantId
  → OTP send / verify
  → 后端：upsert 会员 + 可选 link 商户 + 写首次来源（仅新建时）
  → 前端清 pending；进入 /stores 或直接 pathForMerchant(该店)
```

### 3.1 后端契约（建议）

在现有 OTP verify（或紧随其后的 bootstrap）中支持：

```json
POST /api/v1/member/auth/otp/verify
{
  "phone": "138…",
  "code": "123456",
  "merchant_id": 2   // 可选
}
```

行为：

| 场景 | 行为 |
|------|------|
| 新手机号 + 有 `merchant_id` | 建 `Member`（name 可用手机号尾号占位或「会员」）；`acquisition_source=merchant`，`first_merchant_id=merchant_id`；建 `MerchantMember` |
| 新手机号 + 无 `merchant_id` | 建 `Member`；`acquisition_source=platform`；不建挂靠 |
| 已存在 + 有 `merchant_id` 且未挂靠 | 仅 `MerchantMember`；**不改** `acquisition_source` / `first_merchant_id` |
| 已存在 + 已挂靠 | 幂等成功 |
| `merchant_id` 无效/非本场地/非 active | 422/404，不建脏挂靠 |

权限：公开 OTP 接口；`merchant_id` 必须属于当前站点上下文（与现有会员 OTP 同一 site）。

### 3.2 前端

- `LoginView` 读取 `route.query.merchant_id`，verify 时带上。
- 登录成功：若该店已在 `me.merchants`，可直达业态首页；否则 `/stores`。
- 展示可选：登录页副文案「正在加入：{商户名}」（可先调公开商户简介接口或登录后再提示）。

## 4. 管理端商户二维码

- **入口**：商户列表行操作 + 详情（若有）「获客二维码」。
- **内容**：`{MEMBER_WEB_PUBLIC_URL}/login?merchant_id={id}`（环境变量，如 `VITE_MEMBER_WEB_PUBLIC_URL` / 后端配置回传）。
- **展示**：弹层内 QR 图 + 复制链接 + 下载 PNG（前端生成即可，如 `qrcode` 库）。
- **权限**：`org:read` 且可访问该商户（场地超管看全部；商户员工仅本店）。

## 5. 展示与审计

- `/member/me` 与管理端会员 Out 增加：`acquisition_source`、`first_merchant_id`、`first_merchant_name`（可选拼接）、展示文案「综合运营平台」或商户名。
- 审计：`member.acquire_via_qr` / `member.link_merchant`（新建与仅挂靠可区分）。

## 6. 非目标与后续

- 不在本切片做短链、海报模板、渠道码（员工专属）。
- 列表检索/详情按钮统一规范见姊妹规格 A；本规格只要求**会员相关展示能带出首次来源**。

## 7. 验收清单

- [ ] 迁移后老数据来源符合 §2.3
- [ ] 扫码新用户：主档 + 挂靠 + 来源正确
- [ ] 扫码老用户挂新店：仅新增关联
- [ ] 无参登录新用户：来源=平台
- [ ] 商户页可出码并扫得通（本机/演示域名）
