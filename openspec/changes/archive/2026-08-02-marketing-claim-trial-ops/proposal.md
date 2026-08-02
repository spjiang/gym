## Why

PRD §5.5/§6.2 要求会员端领券与体验卡；现有仅员工发券与普通卡种，获客闭环不完整。

## What Changes

- 券模板支持「可自助领取」与每人限领；会员可查看可领券、领取、查持券
- 会籍卡种支持体验标记（`is_trial`）；后台与 H5 目录展示；购卡履约复用现链路
- **不做**：活动价、裂变、活动码、真短信推券

## Capabilities

### New Capabilities
- `coupon-member-claim`: 会员自助领券与持券查询

### Modified Capabilities
- `coupon-catalog`: 模板增加可领与每人限领配置
- `membership-catalog`: 卡种增加体验标记
- `member-portal`: 会员端领券与体验卡展示/购买入口

## Impact

- 模型与 Alembic 0008；会员/员工 API；frontend Coupons/Products；member-web 领券与商城标注
- 测试：领取限领、体验卡创建与目录
