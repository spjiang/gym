# 会员原生小程序

用微信开发者工具打开本目录。将 `app.js` 中 `apiBase` 指向后端 `/api/v1`（本地 Compose 默认 `http://127.0.0.1:18000/api/v1`），并在开发者工具开启不校验合法域名以便联调。

## 页面

登录 / 选店 / 会籍 / 团课 / 商城（购卡·课包支付）/ 领券。均调用既有会员 API。

## 支付联调

1. 管理端「综合经营 → 支付配置」：`mode=wechat`，开启 **DRY_RUN**，填写小程序 AppID / 商户号 / APIv3 密钥（干跑可不配私钥）。
2. 登录后会 `wx.login` → `POST /member/auth/wechat/mini/bind`。
3. 商城下单 → `pay/online`（`pay_scene=miniprogram`）→ 干跑自动 `pay/dry-run-confirm`；真实模式调 `wx.requestPayment`。
4. OTP 演示码见仓库 `user.md`（默认 `123456`）。

关闭 DRY_RUN 并配置商户 API 私钥、证书序列号、公网 `notify_url` 后即可走真实 APIv3。
