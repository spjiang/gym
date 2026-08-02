## Why

PRD §4.6 要求轻量通知（开卡、预约、支付结果）；本期落地站内通知记录与查询，预留队列投递。

## What Changes

- 新增 notifications 表与写入服务
- 在办卡履约、团课预约、支付成功等钩子写入站内通知
- 员工/会员可查询本人相关通知列表（员工端按商户）
- **仅限本 change 不做**：真短信、微信订阅消息生产投递

## Capabilities

### New Capabilities
- `notification-inbox`: 站内通知写入与查询

### Modified Capabilities
- （无强制修改既有规格；履约钩子为实现细节）

## Impact

- 通知服务、API、前端简单列表；测试写入与列表
