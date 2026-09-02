# 会员原生小程序

用微信开发者工具打开本目录。生产 AppID：`wx90749dbadeb4227a`。`app.js` 的 `apiBase` 当前指向 `https://api.guanyespace.com/api/v1`；本机联调改为 `http://127.0.0.1:18000/api/v1` 并勾选不校验合法域名。

## 与 H5 会员端一致的结构

| 环节 | 行为 |
|------|------|
| 登录后 | 进入 **选店门户** `/pages/stores/index`（Banner、FIT/BAR 分区） |
| 选店 | 按业态进入健身房首页或餐饮点餐 |
| 健身房 | 顶栏（门店名 + 切换 + 我的）+ 底栏：首页/会籍/团课/商城/卡券/我的 |
| 餐饮吧 | 顶栏 + 底栏：点餐/订单/卡券/我的 |
| 切换门店 | 顶栏「切换」或「我的 → 选店」回到门户 |

## 页面

登录 / 选店门户 / 会籍 / 团课 / 商城 / 餐饮 / 领券 / 会员中心。均调用既有会员 API。

## 支付联调

1. 管理端「综合经营 → 支付配置」：`mode=wechat`，开启 **DRY_RUN**，填写小程序 AppID / 商户号 / APIv3 密钥（干跑可不配私钥）。
2. 登录后会 `wx.login` → `POST /member/auth/wechat/mini/bind`。
3. 商城下单 → `pay/online`（`pay_scene=miniprogram`）→ 干跑自动 `pay/dry-run-confirm`；真实模式调 `wx.requestPayment`。
4. OTP 演示码见仓库 `user.md`（默认 `123456`）。

关闭 DRY_RUN 并配置商户 API 私钥、证书序列号、公网 `notify_url` 后即可走真实 APIv3。
