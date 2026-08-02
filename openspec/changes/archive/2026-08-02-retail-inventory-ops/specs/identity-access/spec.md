## ADDED Requirements

### Requirement: 零售相关权限点
系统 SHALL 提供并校验 `retail:manage`、`retail:sell`、`retail:read`；无相应权限 MUST 拒绝对应操作。

#### Scenario: 无售卖权限不可零售下单
- **WHEN** 无 `retail:sell` 与 `retail:manage` 的员工尝试创建零售订单
- **THEN** 系统拒绝
