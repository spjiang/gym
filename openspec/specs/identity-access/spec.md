## Purpose

定义员工账号、预置角色、鉴权与商户数据隔离，以及关键操作的审计能力，作为平台底座主规格长期生效。。。

## Requirements

### Requirement: 预置角色
系统 SHALL 预置并支持分配以下角色：场地超管、商户管理员、前台、教练。

#### Scenario: 为商户员工分配前台角色
- **WHEN** 商户管理员或场地超管为某员工分配前台角色
- **THEN** 该员工登录后仅获得前台权限集

### Requirement: 登录与鉴权
系统 SHALL 要求员工使用有效凭证登录后才能访问受保护的管理 API；未认证请求 MUST 被拒绝。

#### Scenario: 未登录访问受保护接口
- **WHEN** 客户端未提供有效访问令牌请求受保护 API
- **THEN** 系统返回未授权错误且不泄露业务数据

### Requirement: 商户数据隔离
系统 SHALL 确保非场地超管的员工仅能访问其所属商户范围内的数据；场地超管可访问全场地数据。

#### Scenario: 商户管理员越权读取他商户
- **WHEN** 商户 A 的管理员请求商户 B 的受保护资源
- **THEN** 系统拒绝访问或返回无权限

#### Scenario: 超管跨商户访问
- **WHEN** 场地超管请求任意商户的受保护资源
- **THEN** 在权限点允许的前提下系统返回数据

### Requirement: 关键操作审计
系统 SHALL 对角色变更、通行授权变更等关键写操作记录审计日志（操作者、时间、对象、动作摘要）。

#### Scenario: 变更员工角色留下审计
- **WHEN** 管理员修改某员工角色
- **THEN** 系统新增一条可查询的审计记录包含操作者与变更对象

### Requirement: 课程相关权限点
系统 SHALL 提供并校验权限点：`coach:manage`、`course:manage`、`course:book`、`course:checkin`、`pt:sell`；教练角色默认仅具备核销/签到及本人数据只读范围所需权限。

#### Scenario: 无权限不可售课包
- **WHEN** 无 `pt:sell` 与 `course:manage` 的员工尝试购买课包下单
- **THEN** 系统拒绝该请求

### Requirement: 零售相关权限点
系统 SHALL 提供并校验 `retail:manage`、`retail:sell`、`retail:read`；无相应权限 MUST 拒绝对应操作。

#### Scenario: 无售卖权限不可零售下单
- **WHEN** 无 `retail:sell` 与 `retail:manage` 的员工尝试创建零售订单
- **THEN** 系统拒绝

### Requirement: 优惠券权限点
系统 SHALL 提供 `coupon:manage`、`coupon:redeem`、`coupon:read` 并校验。

#### Scenario: 无权限不可发券
- **WHEN** 无 coupon:manage 的员工尝试发券
- **THEN** 系统拒绝

### Requirement: 报表只读权限点
系统 SHALL 提供并校验 `report:read`；默认仅场地超管与商户管理员具备该权限，前台与教练 MUST NOT 默认拥有。

#### Scenario: 无权限不可查报表
- **WHEN** 无 `report:read` 的员工请求经营汇总
- **THEN** 系统拒绝该请求

### Requirement: 器材相关权限点
系统 SHALL 提供并校验 `equipment:manage`、`equipment:repair`、`equipment:read`；管理员默认可管理，前台与教练默认可报修与只读。

#### Scenario: 无权限不可改台账
- **WHEN** 无 equipment:manage 的员工尝试创建器材
- **THEN** 系统拒绝

### Requirement: 管理端菜单按权限裁剪
系统 SHALL 仅向员工展示其权限允许的后台菜单与路由。

#### Scenario: 教练看不到商户组织
- **WHEN** 教练角色登录 Web 后台
- **THEN** 侧栏不展示商户组织与员工角色等无菜单
