## Purpose

定义健身房器材台账的创建、查询与状态维护（与门禁设备分离）。

## Requirements

### Requirement: 维护器材台账
系统 SHALL 允许按商户创建与更新器材，包含名称、分类、资产编号、区域与状态（在用/维修/停用/报废）。

#### Scenario: 创建器材
- **WHEN** 有权限员工提交合法器材信息
- **THEN** 系统保存并可查询

### Requirement: 按状态筛选器材
系统 SHALL 支持按商户与状态列出器材，供前台识别不可用设备。

#### Scenario: 筛选维修中
- **WHEN** 员工按 status=repair 查询
- **THEN** 仅返回维修状态器材
