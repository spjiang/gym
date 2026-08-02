## Why

PRD §5.3 要求临访/体验临时通行；前台需快速为访客发放短期门禁授权并到期失效。

## What Changes

- 新增临访登记：关联会员（可按手机号建档）、门禁点、有效期小时数，自动写 AccessGrant 并同步 Pad
- 列表与撤销临访（同步撤销授权）
- Web 后台「临访」入口
- **仅限本 change 不做**：次数卡扣次通行、体验卡商品化售卖

## Capabilities

### New Capabilities
- `walk-in-visit`: 临访登记与临时通行授权

### Modified Capabilities
- （无）复用既有 access-control 授权能力

## Impact

- 新表 visit_passes、API、前端页；测试覆盖创建与通行
