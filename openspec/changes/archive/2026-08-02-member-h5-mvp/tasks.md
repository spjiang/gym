## 1. 会员鉴权

- [x] 1.1 JWT 支持 typ=member；get_current_member 依赖
- [x] 1.2 OTP send/verify API（开发期 mock 码）+ 配置项
- [x] 1.3 员工 token 访问 /member/* 拒绝的测试

## 2. 会员门户 API

- [x] 2.1 me / memberships / pt-packages / access-events
- [x] 2.2 团课场次列表、预约、取消、我的预约
- [x] 2.3 卡种/课包目录与购卡、买课包下单
- [x] 2.4 会员线上支付本人订单（复用 mock 履约）
- [x] 2.5 门户 API 集成测试（登录→约课→购卡支付）

## 3. member-web 与 Compose

- [x] 3.1 脚手架 member-web（Vue3）登录与 Tab 页
- [x] 3.2 对接会籍/团课/商城/通行页面
- [x] 3.3 Compose + .env.example；本地可访问 :8081
- [x] 3.4 pytest 全绿；回写 PRD §10
