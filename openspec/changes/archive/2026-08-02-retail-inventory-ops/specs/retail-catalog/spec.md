## Purpose

定义商户零售商品分类与 SKU 主数据维护及启停规则。

## ADDED Requirements

### Requirement: 维护商品分类
系统 SHALL 允许商户维护商品分类（名称、排序、启停）。

#### Scenario: 创建分类
- **WHEN** 管理员提交合法分类
- **THEN** 系统保存该分类

### Requirement: 维护零售 SKU
系统 SHALL 允许创建与维护 SKU，至少包含名称、单价、单位、库存预警阈值、所属分类、启停；库存数量为非负整数。

#### Scenario: 创建可售 SKU
- **WHEN** 管理员提交合法 SKU（含预警阈值）
- **THEN** 系统保存且初始库存为 0、状态可售

### Requirement: 停用 SKU 不可新售
系统 SHALL 支持停用 SKU；停用后 MUST NOT 用于新零售订单。

#### Scenario: 停用后不可下单
- **WHEN** SKU 已停用且员工尝试零售下单包含该 SKU
- **THEN** 系统拒绝
