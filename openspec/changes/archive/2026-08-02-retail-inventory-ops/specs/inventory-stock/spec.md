## Purpose

定义库存入库出库盘点、流水记录、低库存预警及禁止负库存约束。

## ADDED Requirements

### Requirement: 入库增加库存
系统 SHALL 支持对 SKU 入库并写入库存流水，库存增加后 MUST 仍为非负整数。

#### Scenario: 入库成功
- **WHEN** 员工对某 SKU 入库正整数数量
- **THEN** 库存增加且存在入库流水

### Requirement: 出库与盘点
系统 SHALL 支持手工出库与盘点调整；任何导致库存小于 0 的操作 MUST 拒绝。

#### Scenario: 出库超过库存拒绝
- **WHEN** 出库数量大于当前库存
- **THEN** 系统拒绝且库存不变

#### Scenario: 盘点设为目标值
- **WHEN** 员工提交盘点目标数量（≥0）
- **THEN** 库存更新为目标值并记录差额流水

### Requirement: 低库存预警列表
系统 SHALL 支持按「库存 ≤ 预警阈值」筛选 SKU 列表。

#### Scenario: 筛选低库存
- **WHEN** 客户端请求低库存列表且某 SKU 库存不高于其阈值
- **THEN** 该 SKU 出现在结果中
