## ADDED Requirements

### Requirement: 管理端菜单按权限裁剪
系统 SHALL 仅向员工展示其权限允许的后台菜单与路由。

#### Scenario: 教练看不到商户组织
- **WHEN** 教练角色登录 Web 后台
- **THEN** 侧栏不展示商户组织与员工角色等无菜单
