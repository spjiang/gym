# 微信支付（小程序 JSAPI + H5）与场地统一配置 — 设计规格

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-05 |
| 状态 | 已落地（P1–P4） |
| 关联 | PRD §4.5 / §6.2；`commerce-skeleton`；`member-miniprogram`；`member-web`；综合经营 RBAC 菜单 |
| 范围 | 场地级微信商户配置（管理端可配）、微信 APIv3 下单与回调、小程序 JSAPI、H5 微信内 JSAPI + 站外 MWEB、小程序会员端能力对齐 H5 主路径 |
| 非目标 | 按商户分账/多商户号；企业付款；Native 扫码付；小程序码获客（获客码仍可用 H5）；订阅消息全量；把 H5 整站塞进 web-view（微信原路退与对账见 `2026-08-05-payment-refund-hardening-design`） |

## 1. 背景与目标

当前线上支付仅为 `ONLINE_PAYMENT_MODE` + 环境变量，微信 Provider 在 `WECHAT_DRY_RUN=false` 时直接 501；管理端无法配置；小程序仅为 API 骨架。需在**综合经营**统一配置**全场地共用的一套微信商户号**，并打通：

- 原生小程序：JSAPI（`wx.requestPayment`）
- 会员 H5：微信内 JSAPI；站外浏览器 MWEB

### 1.1 已确认决策

| 决策点 | 选择 |
|--------|------|
| 支付形态 | 小程序 JSAPI + H5 微信内 JSAPI + H5 站外 MWEB |
| 商户号归属 | **全场地共用一套账号**（不按业态/门店拆商户号） |
| 配置入口 | 综合经营管理系统统一配置 |
| 配置存储 | **场地级落库**；密钥加密；env 仅作首次默认/兜底 |
| 方案 | A：支付配置中心 + 统一支付编排 |

### 1.2 成功标准

- 场地超管可在管理端「支付配置」查看/保存微信凭证（密钥脱敏），无需改 `.env` 即可切换 mock / wechat / dry_run。
- 小程序：登录（OTP + `wx.login` 绑定 openid）→ 选店 → 会籍/团课/商城/领券/清吧点餐主路径可用 → 待支付订单可调起微信支付（DRY_RUN 可伪成功）。
- H5：微信内可 JSAPI 支付；站外可拿到 `mweb_url` 跳转；DRY_RUN 行为与小程序一致。
- 真实模式：统一下单 → 用户支付 → **异步回调**验签后订单变 `paid` 并履约；重复回调幂等。
- 全商户订单共用该套配置；商户侧无需各自填微信商户号。

## 2. 配置模型

### 2.1 表 `site_payment_settings`（每 `site_id` 一行）

| 字段 | 说明 |
|------|------|
| `site_id` | PK/唯一 |
| `mode` | `unconfigured` \| `mock` \| `wechat` |
| `dry_run` | bool，默认 true |
| `mp_app_id` | 小程序 AppID |
| `mp_app_secret_enc` | 小程序 secret（加密） |
| `oa_app_id` | 公众号/网页授权 AppID（H5 微信内 OAuth；可与开放平台一致） |
| `oa_app_secret_enc` | 对应 secret |
| `mch_id` | 微信商户号 |
| `api_v3_key_enc` | APIv3 密钥 |
| `mch_serial_no` | 商户证书序列号 |
| `mch_private_key_enc` | 商户 API 私钥 PEM（加密） |
| `notify_url` | 支付结果通知 URL（公网 HTTPS） |
| `h5_return_url` | MWEB 支付完成回跳（可选，默认会员 H5 订单页） |
| `updated_at` / `updated_by_staff_id` | 审计辅助 |

加密：使用应用 `SECRET_KEY` 派生的对称加密（Fernet 或等价）；库中仅密文。

### 2.2 读取优先级

1. 若该 `site_id` 存在行且 `mode != unconfigured` → 用库配置  
2. 否则回落 `Settings` 环境变量（兼容现网 `.env`）  
3. 管理端「从环境变量导入」可选：一键把当前 env 写入库（secret 明文仅导入时写入后加密）

### 2.3 管理端 API / 菜单

- 权限：`payment:config`（仅 `site_admin` / `*`）；菜单挂在综合经营（`platform`）  
- `GET /api/v1/site/payment-settings`：脱敏 Out（secret 字段仅 `configured: true/false` 或尾号掩码）  
- `PUT /api/v1/site/payment-settings`：部分更新；空字符串表示「不修改该密钥」  
- `POST /api/v1/site/payment-settings/import-env`：从 env 灌库  
- 写操作记 `audit`：`payment_settings.update`

前端：`PaymentSettingsView.vue` + 路由 `/platform/payment-settings`；RBAC `MenuDef` 同步。

## 3. 会员身份与 openid

### 3.1 `members` 扩展（或旁表 `member_wechat_bindings`）

推荐旁表，避免污染主档：

| 字段 | 说明 |
|------|------|
| `member_id` | FK |
| `mp_openid` | 小程序 openid（唯一，可空） |
| `oa_openid` | 公众号/网页 openid（唯一，可空） |
| `union_id` | 若开放平台有则存 |

- `POST /api/v1/member/auth/wechat/mini`：`{ code }` → `jscode2session` → 若已绑定则发 token；未绑定返回 `need_bind` + 临时票据，再与 OTP 登录合并绑定  
- 简化一期也可：**必须先 OTP 登录，再调 bind 接口**挂上 openid（实现更简单，推荐本切片采用）  
  - `POST /api/v1/member/auth/wechat/mini/bind` `{ code }`（需会员 JWT）  
  - `POST /api/v1/member/auth/wechat/oa/bind` `{ code }`（H5 微信内 OAuth code）

### 3.2 H5 场景判断

前端根据 UA / `wx` JS-SDK 环境：

| 场景 | `pay_scene` | openid |
|------|-------------|--------|
| 小程序 | `miniprogram` | `mp_openid` |
| 微信内 H5 | `jsapi_h5` | `oa_openid` |
| 站外 H5 | `mweb` | 不强制 |

未绑定对应 openid 时，JSAPI 下单返回明确错误，引导先绑定。

## 4. 支付编排

### 4.1 Provider 改造

`OnlinePayResult` 扩展为：

```text
ok, message, provider_ref,
pay_scene,
jsapi_params?,   # appId,timeStamp,nonceStr,package,signType,paySign
mweb_url?,
dry_run: bool
```

- `mock`：立即成功语义可保留给**管理端代收**；会员端真实模式禁止「下单即 paid」  
- `wechat` + `dry_run=true`：不调微信，返回伪 `jsapi_params` / 伪 `mweb_url`，并由专用「确认干跑支付」接口或前端二次确认后履约（见 §4.3）  
- `wechat` + `dry_run=false`：调用微信支付 APIv3  
  - 小程序：`/v3/pay/transactions/jsapi`（payer.openid = mp）  
  - 微信内 H5：同 JSAPI（openid = oa）  
  - 站外：`/v3/pay/transactions/h5`

### 4.2 会员下单接口契约变更（破坏性，前后端同发）

`POST /api/v1/member/orders/{id}/pay/online`

Request:

```json
{
  "pay_scene": "miniprogram|jsapi_h5|mweb",
  "client_ip": "可选，MWEB 建议传",
  "return_url": "可选，MWEB 回跳"
}
```

Response（**不再直接把订单标为 paid**，除非 mock 管理端通道）:

```json
{
  "order_id": 1,
  "status": "pending",
  "pay_scene": "miniprogram",
  "dry_run": false,
  "jsapi_params": { "...": "..." },
  "mweb_url": null,
  "provider_ref": "wx..."
}
```

管理端 `POST /orders/{id}/pay/online`：可继续「登记式」即时成功（mock / dry_run），或同样改为预下单；**本切片建议管理端保持现有即时成功行为**（前台代客收款），会员端走异步回调模型。

### 4.3 回调与幂等

- `POST /api/v1/payments/wechat/notify`：验签、解析 `out_trade_no`（建议 `order-{id}` 或独立 `payment_intents` 表）  
- 若订单已 `paid`：返回成功 ACK  
- 若 `pending`：写 `payments`、改 `paid`、走现有 fulfill（会籍/课包/零售/券/餐饮取餐号/通知）  
- DRY_RUN：`POST /api/v1/member/orders/{id}/pay/dry-run-confirm`（仅 `dry_run=true` 可用）模拟回调履约，便于无真商户验收

### 4.4 可选表 `payment_intents`

为避免与「下单即 paid」混淆，建议：

| 字段 | 说明 |
|------|------|
| `id` / `out_trade_no` | 微信商户订单号 |
| `order_id` | FK |
| `scene` | pay_scene |
| `status` | `created` \| `succeeded` \| `closed` |
| `provider_prepay_id` | |
| `amount` | |

回调以 `out_trade_no` 定位 intent → order。

## 5. 小程序完善范围

在复用 `/api/v1/member/*` 前提下，对齐 H5 主路径（不做像素级一致）：

| 页面 | 能力 |
|------|------|
| 登录 | OTP；登录后 bind 小程序 openid |
| 选店 / 首页 | 多商户 + 业态入口 |
| 会籍 | 列表/详情、购卡下单、支付 |
| 团课 | 场次、预约/取消 |
| 课包 | 查看剩余（购课支付若 API 已有则接上） |
| 商城/领券 | 现有页加固 + 支付 |
| 清吧 | 菜单、下单、支付、取餐号、退款申请 |
| 我的 | 资料、openid 绑定状态、订单入口 |

工程：`miniprogram/`；`apiBase` 可配置；README 写清合法域名与联调步骤。

## 6. H5 改造要点

- 支付前：检测环境 → 选 `pay_scene`  
- 微信内：若无 `oa_openid`，走 OAuth 静默/手动授权页再 bind  
- 调起：JSAPI 用微信 JSSDK / 桥；MWEB `location.href = mweb_url`  
- DRY_RUN：调确认接口后刷新订单状态  

获客码逻辑不变（仍进 H5）；支付走本规格。

## 7. 安全与运维

- 密钥永不在 GET 响应明文出现；日志禁止打印 secret / 私钥  
- `notify_url` 必须公网 HTTPS；本地联调可用隧道，文档说明  
- 仅场地超管可改配置  
- 证书轮换：更新序列号 + 私钥即可，无需发版  

## 8. 测试与验收

| 用例 | 期望 |
|------|------|
| 无配置 wechat 模式 | 明确 503/业务码 |
| 保存配置脱敏回读 | secret 不回显 |
| DRY_RUN 小程序支付 | 得伪参数 → confirm → paid + 履约 |
| DRY_RUN H5 mweb | 得伪 url → confirm → paid |
| 真实回调幂等 | 二次 notify 不重复履约 |
| 商户 A/B 订单 | 均使用同一场地配置 |

自动化：扩展 `test_phase1_closing` / 新增 `test_wechat_payment_settings.py`；真实微信联调为手工清单。

## 9. 实现分期（同一规格内）

| 阶段 | 内容 |
|------|------|
| P1 | 配置表 + 管理端菜单/API + Provider 读库 |
| P2 | payment_intents + 会员预下单响应改造 + notify + dry-run confirm |
| P3 | 小程序主路径 + bind openid + JSAPI |
| P4 | H5 双场景支付 + OAuth bind |

## 10. 验收清单

- [ ] 综合经营可见「支付配置」，场地超管可保存/导入 env  
- [ ] 全商户共用该配置  
- [ ] 小程序 JSAPI（含 DRY_RUN）闭环  
- [ ] H5 微信内 JSAPI + 站外 MWEB（含 DRY_RUN）闭环  
- [ ] 回调幂等；订单履约与现网一致  
- [ ] PRD §10 / user.md / README 补充配置与联调说明  
