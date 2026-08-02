## ADDED Requirements

### Requirement: 课程相关权限点
系统 SHALL 提供并校验权限点：`coach:manage`、`course:manage`、`course:book`、`course:checkin`、`pt:sell`；教练角色默认仅具备核销/签到及本人数据只读范围所需权限。

#### Scenario: 无权限不可售课包
- **WHEN** 无 `pt:sell` 与 `course:manage` 的员工尝试购买课包下单
- **THEN** 系统拒绝该请求
