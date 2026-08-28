# MinIO 文件存储 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 附件全部进 MinIO；本机与线上各一套服务；公开图走 8900 / `file.`；启动时幂等迁旧盘文件并改库。

**Architecture:** 后端 `POST /uploads` 用官方 `minio` SDK 写入 `public`/`private` 桶。浏览器读 `FILE_PUBLIC_BASE_URL`；旧 `/api/v1/files/` 图 302、PDF 鉴权代读。lifespan 建桶、扫盘、改图片 URL。

**Tech Stack:** MinIO · Python `minio` SDK · FastAPI · Docker Compose · pytest

**Spec:** `docs/superpowers/specs/2026-08-28-minio-file-storage-design.md`

## Global Constraints

- 注释与交流中文；禁止过时 API
- 本机 MinIO 主机口 8900；线上 `file.` → 8900，控制台不进公网
- pytest 连本机 MinIO，不回退本地盘
- 密钥不进 Git；对象名 `{32hex}.{ext}`
- 只改 `backend/app/` 下真实源码，不要改 `backend/app/app/` 嵌套副本

## File Map

| 路径 | 职责 |
|------|------|
| `backend/app/core/upload_urls.py` | 公开 URL、旧路径识别、库内改写 |
| `backend/app/core/object_store.py` | MinIO 客户端、建桶、put/stat/get/delete |
| `backend/app/core/file_migrate.py` | 启动扫盘 + 改库 |
| `backend/app/systems/platform/api/uploads.py` | 写入 MinIO；GET 兼容 |
| `backend/app/core/config.py` | MinIO 与 `FILE_PUBLIC_BASE_URL` |
| 各业务 `*_IMAGE*_RE` | 改为 `is_stored_image_url` |
| `docker-compose*.yml` · `.env*` · 域名文档 | 服务与 Nginx |

本会话用户已要求「实施」，内联执行，不按任务停下来询问。

---

### Task 1: URL 规则与对象存储 + 上传

- [x] 红测 `tests/test_upload_urls.py`、`tests/test_uploads_minio.py`
- [x] 绿：config、upload_urls、object_store、uploads、lifespan 建桶
- [x] 旧测试改为认公开 URL + 302；去掉靠 `UPLOAD_DIR` 落盘的断言

### Task 2: 启动迁移 + 业务校验

- [x] 红测迁移改写字符串/JSON/正文
- [x] 绿：`file_migrate` 挂 lifespan；各模块图片校验共用 `is_stored_image_url`

### Task 3: Compose / 环境 / 域名文档

- [x] compose 增加 minio（8900 / 9001）；backend 依赖健康检查
- [x] `.env.example`、`.env.production.example`、README、域名文档 `file.`
- [x] 起本机 minio，跑相关 pytest
