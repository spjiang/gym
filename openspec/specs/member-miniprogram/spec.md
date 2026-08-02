## Purpose

定义原生微信小程序工程骨架，对接会员 API。

## Requirements

### Requirement: 原生小程序工程
系统 SHALL 提供可导入微信开发者工具的原生小程序工程，覆盖登录、会籍、团课、商城、领券等会员 API 调用入口。

#### Scenario: 工程可打开
- **WHEN** 开发者用微信开发者工具打开 miniprogram 目录
- **THEN** 可见登录与业务页面骨架并配置后端 API 基址
