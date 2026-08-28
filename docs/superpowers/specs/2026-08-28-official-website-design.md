# 观野SPACE 品牌官网与后台「官网管理」

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-28 |
| 状态 | 已落地 |
| Change 建议名 | `official-website` |
| 范围 | 独立官网 `website-web/`（8082 / `www`）+ 综合管理平台一级菜单「官网管理」+ 公开/员工 API |

## 1. 背景与目标

域名方案已预留 `www.guanyespace.com` 作为品牌站，当前仅有会员端 `m.guanyespace.com` 与后台「基础配置 → 观野SPACE 介绍」。需要对外可运营的品牌官网：介绍 SPACE / FIT / BAR，发布新闻、招聘、招商；配置在观野SPACE 综合管理平台维护。

成功标准：

- 本机/Compose 可通过 **8082** 打开官网；生产 `www.guanyespace.com` 反代到该端口
- 超管在观野SPACE 侧栏看到一级菜单 **官网管理**，下挂六个二级页
- 改首页主视觉、发布一篇新闻后，刷新官网即可看到；草稿/下架详情对访客 404
- 官网页脚电话/地址/营业时间与「观野SPACE 介绍」一致；改官网 Hero 不影响会员端介绍
- 官网无登录、无支付、无招聘/招商表单；主按钮跳到可配置的会员端（或展示小程序提示）

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 定位 | 可运营内容站（品牌展示 + 新闻/招聘/招商） |
| 维护方式 | 混合：首页与品牌页结构化配置；新闻/招聘/招商为文章 |
| 事实 vs 营销 | 地址、电话、营业时间共用 `sites`；官网营销文案单独存 |
| 访客动作 | 只阅读 + 跳转，不留资、不办业务 |
| 工程 | 独立 `website-web/`，与 `member-web` 同模式 |
| 端口 / 域名 | 8082；`www.guanyespace.com`；根域 301 → `www` |
| 生效方式 | 保存后刷新即见；一期不做 HTTP 缓存、不重新构建镜像 |
| 视觉 | 展示向、留白；SPACE 运动/社区、FIT 训练、BAR 夜色；不用管理后台表格风 |

## 3. 范围

包含：

- 新工程 `website-web/`（Vue 3 + Vite + 容器 Nginx，`/api/` 反代 backend）
- Compose 开发/生产增加 `website-web:8082`
- 域名文档改为 `www` → 8082（不再默认 302 到 `m`）
- 表 `website_settings`、`website_articles` 与 Alembic 迁移
- 员工 API `/api/v1/website/*`，公开 API `/api/v1/public/website/*`
- 权限 `website:read` / `website:manage`；platform manifest 菜单
- 管理端一级菜单「官网管理」及六个二级页

不包含：

- 招聘投递、招商意向表、线索跟进
- 官网上购卡、点餐、会员登录
- 自由拖拽 CMS、任意新建栏目/页面
- 多语言、评论、站内搜索、SEO 站点地图生成器
- 把「观野SPACE 介绍」挪出基础配置

## 4. 架构

```
HTTPS :443
        │
   主机 Nginx
        ├── admin.guanyespace.com  → :8080  frontend
        ├── m.guanyespace.com      → :8081  member-web
        ├── www.guanyespace.com    → :8082  website-web（新建）
        └── api.guanyespace.com    → :18000 backend
```

| 调用方 | 前缀 | 鉴权 |
|--------|------|------|
| 官网 | `GET /api/v1/public/website/*` | 无登录；仅已发布 |
| 管理后台 | `/api/v1/website/*` | 员工 JWT；读 `website:read`，写 `website:manage`；超管免检。写入另需场地级账号 |

图片仍走现有 `/api/v1/files/{filename}`（图片本就可匿名读）。官网 Nginx 与 member-web 一样把 `/api/` 反代到 `backend:8000`。

本地开发：`website-web` Vite 端口 **5175**（避免与管理端 5173、会员端 5174 冲突）。

## 5. 官网信息架构

顶栏：首页 · SPACE · FIT · BAR · 新闻 · 招聘 · 招商；右侧「进入会员中心」。无独立「联系我们」页。

| 路径 | 页面 | 数据 |
|------|------|------|
| `/` | 首页 | 站点+首页配置；三品牌入口卡；最新 3 条已发布新闻；页脚联系三件套来自 `sites` |
| `/space` `/fit` `/bar` | 品牌页 | 对应品牌结构化字段 |
| `/news` `/news/:id` | 新闻 | `channel=news` |
| `/jobs` `/jobs/:id` | 招聘 | `channel=jobs` |
| `/partners` `/partners/:id` | 招商 | `channel=partners` |

`:id` 为数字主键，不用 slug。未配置会员端 URL 时隐藏「进入会员中心」；未填小程序提示则不展示小程序入口。

空状态：

- 首页未配：站点名默认「观野SPACE」，纯色主视觉 + 默认副标题 `SPORTS · EVENTS · COMMUNITY`，不白屏
- 品牌正文为空：标题 +「内容筹备中」
- 某频道无已发布文章：列表「暂无内容」，顶栏入口仍在
- 草稿/下架/不存在：详情 404
- 公开接口失败：页面「暂时无法加载」，不展示后端原始错误

## 6. 后台菜单与权限

在 `frontend/src/core/nav/systems.ts` 的 `PLATFORM_MENU_GROUPS` 增加分组 `website`，label **官网管理**（非 `flat`）。

| 二级菜单 | 路径 | 权限 |
|----------|------|------|
| 站点设置 | `/platform/website/settings` | 读/写 website |
| 首页配置 | `/platform/website/home` | 同上 |
| 品牌页面 | `/platform/website/brands` | 一页三个 Tab：SPACE / FIT / BAR |
| 新闻动态 | `/platform/website/news` | 文章 CRUD |
| 招聘信息 | `/platform/website/jobs` | 同上 |
| 招商入驻 | `/platform/website/partners` | 同上 |

`backend/app/systems/platform/manifest.py` 增加权限与 `menu_defs`（`required_any` 含对应权限与 `*`）。`sync_manifests` 启动后超管因 `*` 可见菜单。商户角色包**不**默认授予 `website:*`（官网为场地级运营）。

「基础配置 → 观野SPACE 介绍」保持原位。

## 7. 数据模型

场地级，带 `site_id`。

- 员工接口：始终用 `ctx.site_id`。
- 公开接口：一期单站点，取 `sites` 按 `id` 升序的第一行；没有场地时 `contact` 为空、settings 用默认值。不按 Host 分站点。
- 写入：`website:manage` 且必须是场地级账号（`is_site_wide`）。超管 `is_site_admin` 可写。商户前台即使被误授 `website:*` 也拒绝。

### 7.1 `website_settings`

每站点一行（`UNIQUE(site_id)`）。无行时公开接口按默认值组装，不强制先插入。后台首次保存时 upsert。

| 字段 | 类型 | 说明 |
|------|------|------|
| id | PK | |
| site_id | FK sites | 唯一 |
| site_json | JSON | 站点设置 |
| home_json | JSON | 首页 |
| brands_json | JSON | `{ space, fit, bar }` |
| updated_at | timestamptz | |
| updated_by_staff_id | FK 可空 | |

**site_json**

| 键 | 约束 |
|----|------|
| display_name | 对外站点名，最长 128；空则展示「观野SPACE」 |
| seo_title | 最长 128；空则用 display_name |
| seo_description | 最长 255 |
| logo_url | 系统上传图或空 |
| member_web_url | 可空；空则回退环境变量 `MEMBER_WEB_PUBLIC_URL`；再空则隐藏会员入口 |
| miniprogram_hint | 最长 128；空则不展示小程序提示 |
| footer_note | 最长 255，页脚补充一句 |
| icp_beian | 最长 64，备案号 |

**home_json**

| 键 | 约束 |
|----|------|
| hero_image_url | 系统上传图或空 |
| headline | 最长 128 |
| subheadline | 最长 255 |
| show_space / show_fit / show_bar | bool，默认 true |

**brands_json.\<space\|fit\|bar\>**

| 键 | 约束 |
|----|------|
| title | 最长 64；空则 SPACE→观野SPACE，FIT→观野FIT，BAR→观野BAR |
| cover_image_url | 可空 |
| body | Markdown，可空 |
| gallery_image_urls | 最多 9 张 |
| cta_label | 最长 32，可空则无按钮 |
| cta_url | 可空；有 label 无 url 时按钮不渲染 |

图片 URL 校验与场地介绍相同：`^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$`。

### 7.2 `website_articles`

| 字段 | 说明 |
|------|------|
| id | PK，详情页用 |
| site_id | FK |
| channel | `news` / `jobs` / `partners`，创建后不可改 |
| title | 必填，最长 160 |
| summary | 可空，最长 255，列表用 |
| cover_image_url | 可空 |
| body | Markdown 正文 |
| contact_hint | 可空，最长 255；招聘/招商详情展示「如何联系」 |
| status | `draft` / `published` / `archived` |
| published_at | 首次变为 published 时写入；下架不清空；再发布保持原时间 |
| sort_order | int，默认 0；列表：`sort_order DESC, published_at DESC, id DESC` |
| created_at / updated_at | |
| updated_by_staff_id | 可空 |

删除为物理删除。索引：`(site_id, channel, status, sort_order)`。

## 8. 接口

公开（无登录）：

- `GET /api/v1/public/website`  
  返回 settings 三块（已填或默认）+ `contact: { address, service_phone, business_hours }`（来自当前 `sites` 行）+ `latest_news`（最多 3 条：id、title、summary、cover、published_at）
- `GET /api/v1/public/website/articles?channel=&page=&page_size=`  
  仅 `published`；`channel` 必填且为三频道之一
- `GET /api/v1/public/website/articles/{id}`  
  非 published → 404，与不存在相同（不泄露草稿）

员工：

- `GET /api/v1/website/settings` 无则返回空 JSON 块 + 只读 `contact`（便于运营对照）
- `PUT /api/v1/website/settings` body 含 `site` / `home` / `brands` 之一或多块；只更新提交的块
- `GET /api/v1/website/articles?channel=&status=&q=` 分页，后台可见全部状态
- `POST /api/v1/website/articles` 默认 `draft`
- `PATCH /api/v1/website/articles/{id}` 改字段；不可改 channel
- `POST /api/v1/website/articles/{id}/publish` → published
- `POST /api/v1/website/articles/{id}/archive` → archived
- `DELETE /api/v1/website/articles/{id}` 物理删

写操作记审计日志（沿用 `write_audit`）。公开接口不写审计。

## 9. 前端工程

### 9.1 `website-web/`

对齐 `member-web`：Vue 3 Composition API、Vue Router history、Axios 基地址 `/api/v1`。不用 Element Plus。Markdown 渲染与管理端 `MarkdownView` 同策略（安全子集，不执行脚本）。

页面组件按路由拆：布局、首页、品牌、文章列表、文章详情、404。品牌三页共用一个组件，用路由参数区分。

### 9.2 管理端

`frontend/src/systems/platform/views/` 下新增设置/首页/品牌/文章列表（新闻、招聘、招商可共用列表组件，channel 由路由注入）。文章编辑：标题、摘要、封面上传、Markdown 正文、联系提示、发布/下架。列表遵循现有管理端列表约定（筛选、分页）。

路由挂在 `frontend/src/router/index.ts`，`meta.permissions` 与 manifest 一致。

## 10. 部署与文档

- `docker-compose.yml`、`docker-compose.prod.yml` 增加 `website-web`，端口 `8082:80`，构建 arg `VITE_API_BASE_URL=/api/v1`
- `website-web/nginx.conf` 复制 member-web 模式（`/api/` 反代、`try_files` SPA）
- `docs/域名与线上接入设计.md`：品牌官网改为必须项；流量图增加 `www` → `:8082`；去掉「可 302 到 m」作为默认
- 生产主机 Nginx 增加 `www.guanyespace.com` → `127.0.0.1:8082`（文档给出片段，与 admin/m 并列）

## 11. 测试与验收

后端 pytest（与现有 TestClient 风格）：

- 无 token 读 public 成功；读员工 `/website/settings` 401
- 无 `website:manage` 的员工写接口 403
- 草稿文章 public 详情 404；publish 后 200；archive 后再 404
- public 首页 `contact.service_phone` 等于 site 资料；改 settings.hero 不改 `sites.cover_image_url`
- 非法图片 URL 保存 400
- channel 非法或列表缺 channel → 400

手工/Compose：

1. 超管可见「官网管理」六个二级；无 website 权限账号不可见
2. 保存首页主视觉，打开 `http://localhost:8082` 一致
3. 发新闻 → 首页最新与 `/news` 可见；草稿详情 404
4. 改介绍里的电话，官网页脚变；改官网 headline，会员端选店页不变
5. `docker compose` 中 `website-web` 健康监听 8082

## 12. 风险与后续

- 一期无缓存，流量低可接受；若以后 CDN，需在保存时失效
- 文章无版本历史；误删只能靠备份
- 招商/招聘留资、栏目扩展、SSG/SEO 增强另开切片
- 小程序入口仅文案提示，不接跳转 SDK
