# 综合场地管理系统（Gym Platform）

回龙观公园综合场地：多商户底座 + 健身房业态（一期完整运营将按 OpenSpec 切片持续交付）。  
当前已落地：**工程级平台底座** + **会籍办卡闭环**（卡种 / 办卡续费 / 门禁联动 / 管理后台）。

## 技术栈

| 层 | 选型 |
|----|------|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Element Plus |
| 后端 | FastAPI + SQLAlchemy 2 + Alembic |
| 数据库 | PostgreSQL 16 |
| 部署 | Docker Compose（RabbitMQ 可选 profile `mq`） |

## 目录

```
frontend/     # 管理后台
member-web/   # 会员 H5
backend/      # API 服务
openspec/     # 规格与变更
docs/         # PRD 与协作文档
```

## 快速启动（Docker Compose）

前置：安装并启动 Docker Desktop。

```bash
cp .env.example .env
docker compose up --build -d
```

- 管理后台：http://localhost:8080  
- 会员 H5：http://localhost:8081  
- API 文档：http://localhost:18000/docs  
- 健康检查：http://localhost:18000/health  

默认超管（见 `.env` / `.env.example`）：

- 用户名：`admin`
- 密码：`Admin@123456`

`SEED_DEMO=true`（默认）会幂等写入目录级体验数据，例如：

| 模块 | Demo 内容 |
|------|-----------|
| 商户 | 回龙观自营健身房、回龙观清吧 |
| 员工 | 场地 `site_ops`；健身房 `gym_admin` / `gym_ops` / `coach01`；清吧 `bar_admin` / `bar_ops` / `bar_cashier`（密码均为 `Demo@123456`） |
| 会员 | `13800001001` 张三、`13800001002` 李四、`13800001003` 王五 |
| 门禁 | 正门/侧门/公共门 + 演示 Pad |
| 会籍 | 体验周卡、月卡、季卡、次卡、储值卡 |
| 课程 | 教练档案、私教课包、燃脂操/瑜伽及近几天排课 |
| 零售/券/器材 | 补给与饮品 SKU、满减/折扣券、跑步机等台账 |
| 清吧 | 菜单（气泡水/莫吉托/薯条）；Demo 会员已关联健身房+清吧 |
| 获客 | 商户页「获客码」→ H5 扫码 OTP 自动注册挂靠；无码登录记为综合运营平台 |

会员 H5：`13800001001` + 验证码 `123456` → 选店进入健身或清吧点餐（支付取餐号 / 可退款）。管理端「支付配置」可配微信（全场地共用）；小程序见 `miniprogram/`。

关闭 Demo：在 `.env` 设 `SEED_DEMO=false`。

可选启用 RabbitMQ：

```bash
docker compose --profile mq up -d
```

## 本地开发（不经过 Compose）

### 后端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# 将 DATABASE_URL 指向本地 Postgres，或临时 SQLite
export DATABASE_URL=postgresql+psycopg://gym:gym_dev_password@localhost:5432/gym
export SECRET_KEY=dev-secret
alembic upgrade head
python -m app.seed
uvicorn app.main:app --reload --port 8000
```

### 前端（管理后台）

```bash
cd frontend
npm install
npm run dev
```

### 会员 H5

```bash
cd member-web
npm install
npm run dev
```

开发时 Vite 将 `/api` 代理到 `http://127.0.0.1:18000`（与 Compose 后端端口一致时可改）。

## 验收 / 冒烟

### 自动化测试（后端）

```bash
cd backend
source .venv/bin/activate
pytest -q
```

### Compose 验收清单

1. `curl -sf http://localhost:18000/health` 返回 `ok`  
2. 打开 http://localhost:8080 使用超管登录  
3. 打开 http://localhost:8081 使用已建档手机号 + `123456` 登录  
3. **会籍办卡**：门禁点 → 会籍卡种（绑定门禁）→ 会员办卡并线下收款 → 设备校验放行 → 停卡后拒绝  
4. 在「订单收款」可查看 `membership` 订单  

### API 端到端冒烟（无需 Docker）

```bash
cd backend && source .venv/bin/activate
python ../scripts/smoke_e2e.py
```

覆盖：办卡支付 → 通行放行 → 停卡拒行。

## 安全说明

- **不要**提交真实 `.env`（已在 `.gitignore`）  
- 生产环境务必更换 `SECRET_KEY`、数据库密码、种子超管密码  
- 设备凭证（`X-Device-Code` / `X-Device-Key`）与员工 JWT 分离  

## OpenSpec

- 已归档：`openspec/changes/archive/2026-08-02-platform-foundation-scaffold/`  
- 进行中/已实现：`openspec/changes/membership-card-enrollment/`  

产品 PRD：`docs/superpowers/specs/2026-08-02-gym-prd-modules-design.md`
