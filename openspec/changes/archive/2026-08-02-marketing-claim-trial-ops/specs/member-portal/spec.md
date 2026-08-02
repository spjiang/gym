## ADDED Requirements

### Requirement: 会员端领券入口
系统 SHALL 在会员门户提供可领券列表与领取操作。

#### Scenario: H5 领取
- **WHEN** 已登录会员领取可领模板
- **THEN** 持券列表出现新券

### Requirement: 体验卡在会员目录可见
系统 SHALL 在会员会籍卡种目录中返回体验标记，便于端侧标注。

#### Scenario: 目录含体验字段
- **WHEN** 会员查询会籍卡种目录
- **THEN** 每项包含 is_trial
