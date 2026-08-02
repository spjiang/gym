## Why

会籍办卡与门禁已交付，但健身房仍无法售私教课包、排团课与核销，无法对齐 PRD `docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md` §5.2 / §5.7 与交付对照表 §10。设计规格：`docs/superpowers/specs/2026-08-02-pt-group-class-design.md`。

## What Changes

- 教练档案（绑定员工、启停）
- 私教课包商品与实例：订单类型 `pt_package` → 支付履约 → 核销扣课时
- 团课课程模板、场次排课、简单改派
- 后台代约/取消：满员不可约；须本商户生效会籍；取消释放名额
- 团课签到（出席/未出席，不扣会籍次卡）
- 教练 Web 工作台（仅本人数据）
- 管理后台页面与权限点；测试覆盖主路径

## 后续切片承诺（不在本 change，但一期必须做）

1. 会员小程序/H5 约团课、购课包、支付  
2. 商品库存、营销、报表、器材  
3. 真实微信生产支付联调  

## Non-goals（仅限本 change）

- 本 change 不做会员小程序/H5  
- 本 change 不做候补队列、复杂请假审批  
- 本 change 不做真实微信进件与生产联调（继续线下 + mock）  
- 本 change 不做库存/营销/报表/器材、门禁自动签到、次卡约团课扣次  
- 项目级一期仍不做：酒吧 POS 等（见 PRD §9）

## Capabilities

### New Capabilities

- `coach-profile`: 健身房商户教练档案与启停、绑定员工
- `pt-package`: 私教课包商品、售卖履约、持有实例与核销
- `group-class-schedule`: 团课模板与场次排课、改派
- `group-class-booking`: 后台代约/取消、满员与会籍校验、签到

### Modified Capabilities

- `commerce-skeleton`: 订单类型扩展 `pt_package` 及支付成功履约钩子
- `identity-access`: 新增课程相关权限点并分配到角色

## Impact

- 后端：新模型/迁移、API、履约与预约服务、seed 权限
- 前端：教练/课包/团课/教练工作台页面
- 测试与冒烟：售课、约课、满员、核销
- 归档后回写 PRD §10
