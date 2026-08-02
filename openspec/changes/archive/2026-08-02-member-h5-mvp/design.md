## Context

见 proposal 与 `docs/superpowers/specs/2026-08-02-member-h5-design.md`。后台会籍/团课/支付已具备，本切片补会员端触点。

## Goals / Non-Goals

**Goals**
- `member-web` + `/api/v1/member/*` + 会员 JWT
- 验证码 mock、约课、购卡/买课 mock 支付、通行记录

**Non-Goals（仅限本 change）**
- 微信小程序、短信真发、自助注册、券、零售、约私教、真微信生产支付

## Decisions

1. **独立 `member-web/`** — 与 `frontend/` 解耦，后续小程序可复用同一 API；否决同仓双入口以免权限搅合。
2. **JWT `typ=member`** — deps 分流 `get_current_member` / `get_current_context`；避免混用 staff id。
3. **OTP 开发 mock** — 配置项固定验证码（如 `123456`）；生产接入短信另开切片。
4. **薄封装复用服务** — 会员下单/约课调用现有 fulfillment、course booking 逻辑，仅替换 actor 为会员。
5. **Compose 增 `member-web:8081`** — nginx 反代 `/api` 到 backend。

## Risks / Trade-offs

- [未建档用户无法自助注册] → 文案引导前台开卡；符合一期决策  
- [mock 验证码泄露风险] → 仅非生产环境启用；生产强制真实 OTP  
- [多商户切换遗漏] → H5 强制当前 merchant_id，接口均校验会员-商户关联  

## Migration Plan

无破坏性 schema（若 OTP 落库可加轻量表或内存/缓存）；Compose 增服务；回滚去掉 member-web 与 member 路由即可。

## Open Questions

无（真短信与微信登录留后续）。
