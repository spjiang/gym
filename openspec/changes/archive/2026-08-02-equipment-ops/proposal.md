## Why

PRD §5.8 要求健身房器材台账与报修；门禁 Pad 已落地，但有氧/力量等业态设备仍无管理，前台无法登记报修与查看停用状态。

## What Changes

- 新增器材台账（分类、资产编号、区域、状态等）CRUD
- 新增报修单：创建 → 处理中 → 完成/关闭；可联动器材状态为维修
- Web 后台「器材」页；权限 `equipment:manage` / `equipment:repair` / `equipment:read`
- **仅限本 change 不做**：物联网工况、会员约器械、复杂工单引擎、调拨历史完整链路（本期仅台账状态变更备注）

## Capabilities

### New Capabilities
- `equipment-catalog`: 器材台账维护与状态
- `equipment-repair`: 报修单流转

### Modified Capabilities
- `identity-access`: 增加器材相关权限点

## Impact

- 后端模型/迁移/API、seed 权限、前端页面
- 测试：建档、报修、权限隔离
