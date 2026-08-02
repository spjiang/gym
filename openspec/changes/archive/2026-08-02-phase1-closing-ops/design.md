## Decisions

- 活动价字段挂在产品表上（promo_price + 时间窗），服务函数 `effective_price`
- 微信：Provider 校验证书；`WECHAT_DRY_RUN=true` 时用凭证校验后返回 dry-run 成功（便于无真实商户联调）
- OTP：`MemberOtpChallenge` 表；mode=mock|http
- 菜单：前端 `can(perm)`；路由 meta.permissions
- 小程序：原生 JS 骨架，与 H5 共用 API

## Migration

Alembic 0009
