## Purpose

定义前后端分离工程与 Docker Compose 本地运行约定，使开发与验收具备可重复的启动与健康检查基线。

## Requirements

### Requirement: 仓库具备可独立构建的前后端工程
系统 SHALL 在仓库根下提供独立的 `frontend/`（Vue）与 `backend/`（Python）工程，各自拥有依赖清单与可执行的开发/构建入口。

#### Scenario: 工程目录存在且可识别
- **WHEN** 检查员查看仓库根目录
- **THEN** 存在 `frontend/` 与 `backend/`，且各自包含可识别的项目清单文件（如 `package.json` 与 Python 依赖文件）

### Requirement: Compose 编排核心依赖
系统 SHALL 通过根目录 Docker Compose 编排至少 `backend`、`frontend`（或静态托管）、`postgres` 服务；RabbitMQ 可按配置可选启用。

#### Scenario: 本地一键拉起依赖与应用
- **WHEN** 使用者按文档执行 Compose 启动命令且环境变量已按 `.env.example` 配置
- **THEN** PostgreSQL 与后端 API 健康检查通过，前端可通过约定端口访问

### Requirement: 配置与密钥分离
系统 SHALL 通过环境变量注入数据库连接等敏感配置，仓库提供 `.env.example`，且不得要求将真实密钥提交到版本库。

#### Scenario: 缺少密钥时有示例可循
- **WHEN** 新成员克隆仓库
- **THEN** 可依据 `.env.example` 与 README 完成本地配置，而仓库中不包含真实生产密钥

### Requirement: Compose 编排会员 H5
系统 SHALL 在根目录 Docker Compose 中编排独立的会员 H5 服务（或等效静态托管），使其可通过约定端口访问并调用同一后端 API。

#### Scenario: 本地可访问会员 H5
- **WHEN** 使用者按文档启动 Compose 且包含会员 H5 服务
- **THEN** 可通过约定端口打开会员端页面

### Requirement: 仓库包含小程序与生产通道配置示例
系统 SHALL 在根目录提供 miniprogram 工程与 .env.example 中微信/短信相关配置项说明。

#### Scenario: 示例可复制
- **WHEN** 新环境按 .env.example 配置
- **THEN** 可见 ONLINE_PAYMENT_MODE=wechat 与 OTP 模式相关键
