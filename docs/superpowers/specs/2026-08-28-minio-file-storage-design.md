# 附件全部进 MinIO（file 子域）

| 项 | 内容 |
|----|------|
| 日期 | 2026-08-28 |
| 状态 | 已落地 |
| Change 建议名 | `minio-file-storage` |
| 范围 | Compose 增加 MinIO；上传写入对象存储；公开图走 `file.`；旧盘文件启动时迁入；本机与线上各一套桶 |

## 1. 背景与目标

附件目前写在后端 `UPLOAD_DIR`，对外地址是 `/api/v1/files/{uuid}.ext`。官网、H5、小程序 `<img>` 都打 API；生产没有独立文件域，也不便横向扩存储。

成功标准：

- 新上传只进 MinIO，不再落盘作为主存储
- 本机浏览器能用 `http://localhost:8900/public/...` 出图；线上用 `https://file.guanyespace.com/{文件名}`
- 本机与线上各跑一套 MinIO，数据、密钥互不共用
- 启动后 `UPLOAD_DIR` 里已有文件出现在本环境的桶里；库里图片字段改为公开 URL
- 旧 `/api/v1/files/{name}` 仍可用（图 302，PDF 鉴权后从私有桶读）
- MinIO 控制台不挂到 `file.`

## 2. 已确认决策

| 项 | 决策 |
|----|------|
| 存放 | 所有附件进 MinIO，不用本机目录当生产存储 |
| 上传入口 | 仍 `POST /api/v1/uploads`，后端 SDK 写入，返回公开绝对 URL（PDF 仍返回 `/api/v1/files/...`） |
| 文件域 | `file.guanyespace.com` 只给访客读对象；控制台不进该域 |
| 环境 | 本地 Compose 一套 MinIO，生产 Compose 另一套 |
| 主机端口 | 容器内 9000，映射主机 **8900**（`8900:9000`） |
| 测试 | pytest 连本机 MinIO，不连线上、不回退本地盘 |
| 旧数据 | 后端启动时幂等扫盘上传 + 改库里图片 URL；磁盘先不删 |
| 控制台 | 本机 `localhost:9001`；线上仅 `127.0.0.1:9001` |

## 3. 范围

包含：

- `docker-compose.yml` 与 `docker-compose.prod.yml` 增加 `minio`；backend `depends_on` MinIO 健康
- 环境变量：`MINIO_*`、`FILE_PUBLIC_BASE_URL`（密钥不进 Git）
- 后端：`minio` SDK、建桶与匿名读策略、上传改写、`GET /files/` 兼容
- 统一图片 URL 校验（旧相对路径 + 当前 `FILE_PUBLIC_BASE_URL`）
- 启动迁移：盘 → 桶；库内图片前缀替换
- 域名文档：DNS `file`、Nginx 反代 8900、小程序 downloadFile 增加 `file.`
- 测试改为打本机 MinIO

不包含：

- 前端直传 / 预签名直传
- 把 MinIO Console 挂到公网或 `file.`
- 本机与线上互相同步对象
- 自动删除 `UPLOAD_DIR`（迁完确认后再手工清）
- 图片处理（缩略图、WebP 转码、CDN）

## 4. 架构

```
本机 docker-compose.yml
  minio :9000 → 主机 8900（浏览器读 public）
  控制台 9001
  backend MINIO_ENDPOINT=minio:9000
  FILE_PUBLIC_BASE_URL=http://localhost:8900/public

生产 docker-compose.prod.yml
  minio :9000 → 主机 8900（建议 127.0.0.1:8900，不直接对公网）
  控制台 127.0.0.1:9001
  主机 Nginx：file.guanyespace.com:443 → 127.0.0.1:8900/（file-gateway 已转到 public 桶，勿再拼 /public/）
  FILE_PUBLIC_BASE_URL=https://file.guanyespace.com/public
```

流量（生产）：

```
HTTPS :443
        │
   主机 Nginx
        ├── admin. / m. / www. / api.   （现有）
        └── file.guanyespace.com  → :8900  MinIO path-style「public 桶」
                                    不反代 Console
```

桶：

| 桶 | 用途 | 公网 |
|----|------|------|
| `public` | jpg / png / webp | 匿名 GET |
| `private` | PDF 证照 | 否；仅后端带密钥读写，员工登录后由 `GET /api/v1/files/` 代读 |

对象名与现文件名相同：`{32 位 hex}.{jpg\|png\|webp\|pdf}`。

后端在 Compose 网络内访问 `minio:9000`（path-style）。返回给浏览器的必须是 `FILE_PUBLIC_BASE_URL`，不能是容器主机名。

生产 8900：与域名文档一致，同机 Nginx 用 `127.0.0.1:8900`，compose 映射 `127.0.0.1:8900:9000`。若运维 Nginx 只能打公网 IP，则映射 `8900:9000` 且防火墙/安全组不对公网开放 8900（只放行 80/443）。

## 5. URL 规则

| 环境 | 图片（新） | PDF |
|------|-----------|-----|
| 本地 | `http://localhost:8900/public/{文件名}` | `/api/v1/files/{文件名}` |
| 线上 | `https://file.guanyespace.com/{文件名}` | 同上 |

线上 Nginx 把 `https://file.guanyespace.com/{文件名}` 转到 MinIO ` /public/{文件名}`，地址里不出现桶名。

`POST /uploads`：图返回上述公开 URL；PDF 仍返回 `/api/v1/files/{文件名}`。

`GET /api/v1/files/{filename}`（兼容旧 H5/小程序缓存）：

- 非法文件名 → 404
- 图：302 到 `{FILE_PUBLIC_BASE_URL}/{文件名}`（对象不存在则 404）
- PDF：校验员工 JWT 后从 `private` 流式返回；无令牌 401

图片校验（场地介绍、活动、菜品、SKU、教练、官网等）统一认两种：

1. `^/api/v1/files/[0-9a-f]{32}\.(jpg|png|webp)$`
2. `^{转义后的 FILE_PUBLIC_BASE_URL}/[0-9a-f]{32}\.(jpg|png|webp)$`

禁止任意外链。实现抽到一处（例如 `app/core/upload_urls.py`），各业务模块共用。

`String(255)` 字段装得下上述两种新地址，一期不加列长。

## 6. 启动时迁移（幂等）

`lifespan` 在 MinIO 可达后执行，失败则启动失败（不要静默改回本地盘）：

1. 确保桶存在；`public` 设置匿名只读 GetObject（仅该桶）。
2. 扫描 `UPLOAD_DIR` 一层文件（忽略子目录与非法名）：
   - `.jpg` `.png` `.webp` → `public/{文件名}`
   - `.pdf` → `private/{文件名}`
   - 对象已存在则跳过
3. 改库：把仍以 `/api/v1/files/` 开头且扩展名为图的字符串，替换为 `{FILE_PUBLIC_BASE_URL}/{文件名}`。PDF 与非图扩展名不改。

扫描范围（字符串列 + JSON 里的字符串 + 官网 Markdown 正文）：

| 来源 | 字段 |
|------|------|
| 场地 | `cover_image_url`、`banner_image_urls`、`gallery_image_urls` |
| 商户 | `cover_image_url`、`gallery_image_urls`；`license_image_url` 仅当为图时替换 |
| 会员 | `avatar_url` |
| 教练 | `avatar_url`、`intro_image_urls` |
| 活动 | `cover_url` |
| 零售 SKU | `image_urls` |
| 餐饮菜品 | `image_url` |
| 官网设置 | `site_json` / `home_json` / `brands_json` 中的图片键 |
| 官网文章 | `cover_image_url`、`body` 中的 `/api/v1/files/{uuid}.(jpg\|png\|webp)` |

迁完磁盘文件保留。读路径一律 MinIO。清盘不在本期自动做。

本机启动只迁本机卷；线上只迁线上卷。两边桶不相通。

## 7. 配置

`.env.example`（示例值，生产另写）：

```env
MINIO_ENDPOINT=minio:9000
MINIO_ACCESS_KEY=gymminio
MINIO_SECRET_KEY=change-me-minio-secret
MINIO_USE_SSL=false
FILE_PUBLIC_BASE_URL=http://localhost:8900/public
```

生产 `.env`：`FILE_PUBLIC_BASE_URL=https://file.guanyespace.com/public`（与 MinIO `8900:9000` path-style 一致）；密钥与本机不同。`UPLOAD_DIR` 仍指向现有卷，供启动扫描。

Compose `minio`：官方镜像；数据卷独立（本机 `minio_data` / 生产 `minio_data` 各环境一份）。健康检查用 MinIO live 探针。

依赖：Python 包 `minio`（官方 SDK，非过时 API）。

## 8. 域名与小程序

`docs/域名与线上接入设计.md` 增补：

- DNS：`file` A 记录 → `123.56.26.229`
- Nginx：`file.guanyespace.com` → `http://127.0.0.1:8900/`（file-gateway 已转到 public 桶；或运维实际可达的主机 IP:8900）；证书覆盖 `file`
- HTTP 80 跳转名单加上 `file.guanyespace.com`
- 微信 downloadFile 合法域名增加 `https://file.guanyespace.com`（request 仍走 `api.`）

CORS：`<img>` 跨域加载不要求 `file.` 进 `CORS_ORIGINS`。

## 9. 测试

- pytest 使用本机 MinIO（`MINIO_ENDPOINT=127.0.0.1:8900` 或测试夹具覆盖）。compose 未起 MinIO 时失败并提示，不写临时盘。
- 上传用例断言返回 URL 以当前 `FILE_PUBLIC_BASE_URL` 开头（图）或 `/api/v1/files/`（PDF）。
- 测图仍用 `{uuid}.ext`（校验正则要求如此）；用例结束删除该对象，避免堆满本地 `public` 桶。
- 覆盖：匿名 GET 公开图；PDF 无令牌 401；`GET /files/{旧图}` 302。

## 10. 风险与运维

- 生产勿把 Console 和 8900 暴露到安全组公网。
- 启动迁移对大目录是同步扫描，现有体量（单层 uuid 文件）可接受。
- 官网/H5 存的是绝对 URL：本机库里的 `localhost:8900` 不能拿到线上看；这是两套存储的预期行为。
