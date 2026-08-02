# 会员 H5 MVP 设计

**状态：** 已批准（2026-08-02）  
**Change 建议名：** `member-h5-mvp`  
**对齐 PRD：** §6.2 会员小程序/H5（本切片仅 H5 MVP）

## 1. 目标

交付独立会员端 Vue H5，使已建档会员可完成：登录、查会籍/课包、约/取消团课、购卡/买课包并 mock 线上支付、查看本人通行记录。

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 端形态 | 独立 `member-web/`（Vue3），非微信原生小程序 |
| 登录 | 手机号 + 验证码；开发期 mock 固定码；一期不开放自助注册 |
| 范围 | MVP：查卡、约团课、购卡/买课、mock 支付、通行记录 |
| 工程 | 方案 1：独立工程 + `/api/v1/member/*` + 会员 JWT |
| 支付 | 仅线上入口，沿用现有 mock；真微信后续切片 |
| 不做 | 领券、零售、约私教、短信真发、自助注册、小程序、推送 |

## 3. 工程结构

- `member-web/`：Vue3 + Vite，移动端单栏 + 底部 Tab
- Compose 增加 `member-web`（建议端口 `8081`），反代后端 `/api/v1`
- 管理后台 `frontend/` 不变

## 4. 鉴权

- 会员 JWT：`sub=member_id`，`typ=member`，与员工 token 隔离
- `/api/v1/member/*` 使用 `get_current_member`；员工 token 必须拒绝
- 流程：`otp/send` → `otp/verify` → 发 JWT；手机号须已存在会员主档
- 未建档：返回明确错误（请到前台开卡）

## 5. 页面与 API

### 5.1 页面

登录｜我的｜会籍与课包｜团课｜商城（卡种/课包）｜通行记录；多商户时顶栏切换当前商户。

### 5.2 API 清单

- `POST /member/auth/otp/send`、`/member/auth/otp/verify`（公开）
- `GET /member/me`
- `GET /member/memberships`、`GET /member/pt-packages`
- `GET /member/group-sessions`、`GET|POST /member/group-bookings`、`DELETE /member/group-bookings/{id}`
- `GET /member/catalog/membership-products`、`GET /member/catalog/pt-products`
- `POST /member/orders/membership`、`POST /member/orders/pt-package`
- `POST /member/orders/{id}/pay/online`、`GET /member/orders/{id}`
- `GET /member/access-events`

实现复用现有领域服务（履约、约课等），会员层只做鉴权与本人范围过滤。

## 6. 支付与商户

- 会员侧仅线上支付；mock 成功后走现有履约钩子
- 目录/约课/购卡按当前 `merchant_id` 过滤

## 7. 验收标准

1. 已建档会员可用固定验证码登录 H5  
2. 可查看会籍与私教剩余课时  
3. 可自助约/取消团课  
4. 可购卡或买课包并用 mock 线上支付完成履约  
5. 可查看本人通行记录  
6. 员工 token 无法调用 `/member/*`

## 8. 风险与后续

- 真短信与微信登录/支付需单独切片  
- 原生小程序可复用同一套 `/member` API  
- 券、门店信息、人脸状态展示为后续增量
