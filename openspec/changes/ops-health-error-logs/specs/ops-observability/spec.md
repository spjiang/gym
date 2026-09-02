## Purpose

为场地运维提供服务就绪探查、请求追踪与系统错误采集，使业务拒单与通道/程序故障可在后台区分并关联查询。

## ADDED Requirements

### Requirement: 探活与探就绪分离
系统 SHALL 提供无登录的进程探活与依赖探就绪接口。探活仅表示进程可响应；探就绪在 Postgres 不可用时 MUST 返回失败。MinIO 异常 SHALL 标记为降级，不得单独使探就绪整体失败。Docker 健康检查 MUST 继续使用探活，避免依赖抖动导致容器被拉起循环。

#### Scenario: 进程存活
- **WHEN** 调用探活接口且进程正常
- **THEN** 返回成功状态

#### Scenario: 数据库不可用
- **WHEN** Postgres 无法连接
- **THEN** 探就绪返回失败，探活仍可成功

#### Scenario: 对象存储降级
- **WHEN** Postgres 正常而 MinIO 不可达
- **THEN** 探就绪整体仍成功，并标明 MinIO 异常

### Requirement: 请求标识贯穿响应与日志
系统 SHALL 为每个 HTTP 请求分配 `request_id`，并在响应头 `X-Request-ID` 中返回。写操作审计记录 SHALL 保存同一 `request_id`。系统错误记录 SHALL 保存同一 `request_id`，以便与操作日志对上。

#### Scenario: 探活也带追踪头
- **WHEN** 调用探活接口
- **THEN** 响应包含非空的 `X-Request-ID`

#### Scenario: 写操作审计带 request_id
- **WHEN** 已登录用户发起会被审计的写请求
- **THEN** 对应操作日志包含该请求的 `request_id`

### Requirement: 系统错误进入错误事件
系统 SHALL 将下列情况写入错误事件（含截断后的文案；未捕获异常 MUST 含堆栈）：未捕获异常、HTTP 5xx、支付通道/配置/回调解密或找不到单/金额不一致/履约失败、建单过程中的未捕获或提交失败。错误事件 MUST 使用独立会话写入，不得因业务事务回滚而丢失。默认保留 30 天。

#### Scenario: 未捕获异常
- **WHEN** 接口抛出未处理异常
- **THEN** 客户端收到 500，且错误事件中能按该请求检索到堆栈与 `request_id`

#### Scenario: 支付回调失败落库
- **WHEN** 微信支付回调因非法 JSON、解密失败、找不到支付单或履约失败而向微信返回 FAIL
- **THEN** 系统写入一条错误事件，并尽量带上订单号或商户订单号

### Requirement: 业务拒单不进入错误事件
系统 SHALL NOT 将用户可自行纠正的业务拒绝写入错误事件，包括但不限于：参数校验失败、权限不足、商品/卡种不存在或停用、空购物车、金额非法、未绑定 openid、用户未支付或取消支付、订单状态机拒绝的常规操作。此类失败若属于写操作，SHALL 仍记入操作日志 failure，并在详情中包含错误码与提示文案。

#### Scenario: 建单校验失败
- **WHEN** 创建订单因金额非法或标题为空被拒绝
- **THEN** 不产生错误事件，操作日志（若该请求会被审计）标记为失败并带错误码

### Requirement: 运维后台可查服务状态与错误
具备 `devops:read` 的员工 SHALL 能在综合经营「运维管理」中查看服务状态与错误日志。服务状态接口 MUST 需登录，不得把内部依赖详情暴露给公开探活。错误日志 MUST 支持按时间、模块、错误码、关键词、`request_id` 筛选，详情可展示堆栈与关联 `request_id`。无该权限的账号 MUST 无法访问上述接口与菜单。场地运营人员 SHALL 被授予 `devops:read`；操作日志仍使用既有 `audit:read`。

#### Scenario: 超管查看运维页
- **WHEN** 场地管理员打开导航
- **THEN** 运维管理下可见操作日志、错误日志、服务状态

#### Scenario: 无权限拒绝
- **WHEN** 未授予 `devops:read` 的账号请求错误日志或服务状态接口
- **THEN** 系统拒绝访问

### Requirement: 敏感信息与堆栈隔离
系统 SHALL NOT 将堆栈写入操作日志。错误事件与标准输出中的请求体 MUST 脱敏（密码、token 等）。微信回调密文 MUST NOT 完整入库，仅保留截断错误文案与业务单号。

#### Scenario: 操作日志无堆栈
- **WHEN** 未捕获异常导致写操作失败
- **THEN** 操作日志详情不含堆栈，错误事件含截断堆栈
