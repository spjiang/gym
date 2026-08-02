## ADDED Requirements

### Requirement: Compose 编排会员 H5
系统 SHALL 在根目录 Docker Compose 中编排独立的会员 H5 服务（或等效静态托管），使其可通过约定端口访问并调用同一后端 API。

#### Scenario: 本地可访问会员 H5
- **WHEN** 使用者按文档启动 Compose 且包含会员 H5 服务
- **THEN** 可通过约定端口打开会员端页面
