## ADDED Requirements

### Requirement: 报表只读权限点
系统 SHALL 提供并校验 `report:read`；默认仅场地超管与商户管理员具备该权限，前台与教练 MUST NOT 默认拥有。

#### Scenario: 无权限不可查报表
- **WHEN** 无 `report:read` 的员工请求经营汇总
- **THEN** 系统拒绝该请求
