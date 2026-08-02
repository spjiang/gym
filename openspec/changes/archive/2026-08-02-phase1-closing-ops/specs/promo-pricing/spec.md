## ADDED Requirements

### Requirement: 配置限时活动价
系统 SHALL 允许为会籍卡种、零售 SKU、私教课包配置活动价与有效时间窗。

#### Scenario: 活动期内下单用活动价
- **WHEN** 当前时间落在活动窗且活动价有效
- **THEN** 订单金额采用活动价

#### Scenario: 活动外用原价
- **WHEN** 不在活动窗或未配置活动价
- **THEN** 订单金额采用原价
