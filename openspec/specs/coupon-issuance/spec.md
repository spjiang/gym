## Purpose

定义向会员发放优惠券及查询持券状态。

## Requirements

### Requirement: 向会员发券
系统 SHALL 支持将启用中的券模板发放给指定会员，生成未使用券实例。

#### Scenario: 发券成功
- **WHEN** 员工为会员发放可用模板
- **THEN** 会员持有一张 unused 状态的券
