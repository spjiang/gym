# 观野SPACE 品牌官网 Implementation Plan

> **For agentic workers:** 本会话内联执行（用户已要求实施）。

**Goal:** 独立官网 `website-web`（8082/`www`）+ 后台一级菜单「官网管理」维护结构化配置与新闻/招聘/招商文章。

**Architecture:** 场地级 `website_settings`（JSON 三块）+ `website_articles`。员工 JWT 写 `/api/v1/website/*`；访客只读 `/api/v1/public/website/*`。地址/电话/营业时间读 `sites`，不另存。

**Tech Stack:** FastAPI · Alembic · pytest · Vue 3 · Vite · Docker Compose

**Spec:** `docs/superpowers/specs/2026-08-28-official-website-design.md`

## Global Constraints

- 注释与交流中文；禁止过时 API
- 官网无登录、无支付、无留资表单
- 商户角色包不默认授予 `website:*`；写入必须场地级账号
- 一期无 HTTP 缓存；文章物理删除；详情用数字 id

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/systems/platform/models/website.py` | `WebsiteSettings` / `WebsiteArticle` |
| `backend/alembic/versions/20260828_0046_website.py` | 迁移 |
| `backend/app/systems/platform/services/website.py` | 默认值、图片校验、组装公开/员工 DTO、频道常量 |
| `backend/app/systems/platform/api/website.py` | 员工 CRUD |
| `backend/app/systems/platform/api/public_website.py` | 公开只读 |
| `backend/app/systems/platform/manifest.py` | 权限与六个菜单 |
| `backend/tests/test_website.py` | 规格 §11 行为 |
| `frontend/.../WebsiteSettingsView.vue` 等 | 官网管理六页 |
| `website-web/` | 访客 SPA |
| `docker-compose*.yml` · 域名文档 | 8082 / www |

---

### Task 1: 后端模型、服务、公开/员工 API

- [x] 红测 `test_website.py`
- [x] 绿：模型、迁移、服务、两套 API、manifest、挂载 main、models 门面

### Task 2: 管理端「官网管理」

- [x] `PLATFORM_MENU_GROUPS` + 路由 + Layout 图标
- [x] 站点设置 / 首页 / 品牌 Tab / 文章列表（channel 注入）

### Task 3: `website-web` + Compose + 域名文档

- [x] 对齐 member-web 的 Vue3 工程，端口 5175 / 容器 8082
- [x] compose 增加服务；域名文档 www → 8082
- [x] `pytest tests/test_website.py` 通过
