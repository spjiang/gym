## ADDED Requirements

### Requirement: 器材相关权限点
系统 SHALL 提供并校验 `equipment:manage`、`equipment:repair`、`equipment:read`；管理员默认可管理，前台与教练默认可报修与只读。

#### Scenario: 无权限不可改台账
- **WHEN** 无 equipment:manage 的员工尝试创建器材
- **THEN** 系统拒绝
