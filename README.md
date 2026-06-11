# AI Workbench

企业智能协作工作台 — 基于增强 RAG + 多 Agent + LangGraph 工作流。

技术栈：Vue 3 + FastAPI + PostgreSQL 16 + Redis 7 + Nginx。

## 前置要求

- [Docker](https://docs.docker.com/get-docker/) 25.x + [Docker Compose](https://docs.docker.com/compose/) 2.x
- 本地手动开发额外需要：
  - Node.js 20+、pnpm / npm
  - Python 3.11+
  - PostgreSQL 16、Redis 7

## 11.1 环境准备

| 组件 | 版本 | 用途 |
|------|------|------|
| Docker | 25.x | 容器运行时 |
| Docker Compose | 2.x | 多服务编排 |
| PostgreSQL | 16 | 业务数据持久化 |
| Redis | 7 | 缓存、限流、监控统计 |
| Nginx | 1.25 | 反向代理与统一入口 |
| Python | 3.11 | 后端运行时 |
| Node.js | 20+ | 前端构建与开发 |

## 11.2 依赖安装

### Docker 一键部署（推荐）

```bash
cp .env.example .env
# 编辑 .env，至少配置 JWT_SECRET_KEY 与所需 AI API Key
docker compose up -d --build
```

### 本地手动开发

```bash
# 基础设施
docker compose up -d postgres redis

# 后端
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 前端
cd frontend
npm install
npm run dev
```

## 11.3 配置文件说明

复制 `.env.example` 为 `.env` 后，重点配置项如下：

| 变量 | 说明 | 必填 |
|------|------|------|
| `JWT_SECRET_KEY` | JWT 签名密钥，生产环境使用强随机值 | 是 |
| `DATABASE_URL` | PostgreSQL 连接串 | 是 |
| `REDIS_URL` | Redis 连接串（限流与监控依赖） | 是 |
| `OPENAI_API_KEY` | OpenAI / GPT 模型 | RAG/Agent 需要 |
| `COHERE_API_KEY` | RAG 重排序 | 可选 |
| `TAVILY_API_KEY` | Agent 联网搜索 | 可选 |
| `RATE_LIMIT_ENABLED` | 是否启用接口限流 | 建议 true |
| `RATE_LIMIT_REQUESTS` | 限流窗口内最大请求数 | 默认 100 |
| `NGINX_HTTP_PORT` | Nginx 对外端口 | 默认 80 |

完整变量说明见 [.env.example](.env.example)。

## 11.4 分步部署命令

```bash
# 1. 克隆并进入项目
cd ai-workbench

# 2. 配置环境变量
cp .env.example .env

# 3. 构建并启动全部服务（含 Nginx）
docker compose up -d --build

# 4. 执行数据库迁移（首次部署）
docker compose exec backend alembic upgrade head

# 5. 查看服务状态
docker compose ps
```

## 11.5 启动验证方法

| 检查项 | 地址 / 命令 | 预期结果 |
|--------|-------------|----------|
| Nginx 统一入口 | http://localhost | 前端登录页 |
| 前端直连（开发） | http://localhost:5173 | 前端登录页 |
| 后端健康检查 | http://localhost:8000/api/v1/health | `status: healthy` |
| 监控健康检查 | http://localhost:8000/api/v1/monitor/health | 数据库与 Redis 均为 healthy |
| API 文档 | http://localhost:8000/docs | Swagger UI |
| 默认登录 | `admin` / `admin123` | 登录成功 |
| 监控面板 | 登录后访问「监控面板」菜单 | ECharts 图表正常展示 |

```bash
# 查看后端日志
docker compose logs -f backend

# 查看 Nginx 日志
docker compose logs -f nginx
```

## 11.6 常见部署问题排查

**后端无法连接数据库**

- Docker 模式：`DATABASE_URL` 主机名应为 `postgres`
- 本地模式：主机名改为 `localhost`，确认 PostgreSQL 已启动

**Redis 连接失败导致限流/监控异常**

- 确认 `REDIS_URL=redis://redis:6379/0`（Docker）或 `redis://localhost:6379/0`（本地）
- 执行 `docker compose ps redis` 检查 Redis 健康状态

**前端 API 请求 404 或跨域**

- 经 Nginx 访问时，`VITE_API_BASE_URL` 应为 `/api/v1`
- 检查 `CORS_ORIGINS` 是否包含前端访问地址

**接口返回 429 请求过于频繁**

- 调整 `.env` 中 `RATE_LIMIT_REQUESTS` 或 `RATE_LIMIT_WINDOW_SECONDS`
- 开发调试可临时设置 `RATE_LIMIT_ENABLED=false`

**监控面板无数据**

- 需先产生 API 调用或大模型对话（Token 消耗记录写入 `token_usage` 表）
- 确认当前用户拥有 `monitor:read` 权限（管理员默认拥有 `*`）

## 服务架构

```
                    ┌─────────┐
                    │  Nginx  │ :80
                    └────┬────┘
           ┌───────────────┼───────────────┐
           ▼               ▼               ▼
      /api/* →       /docs →          / → frontend:5173
      backend:8000   backend:8000

postgres:5432 ──┐
                ├── backend
redis:6379   ───┘
```

## 项目结构

```
ai-workbench/
├── backend/           # FastAPI 后端
│   └── app/
│       ├── api/v1/monitor.py      # 系统监控接口
│       ├── core/rate_limit.py     # 接口限流
│       └── services/monitor_service.py
├── frontend/          # Vue 3 前端
│   └── src/views/monitor/Dashboard.vue
├── nginx/             # Nginx 反向代理配置
├── docker-compose.yml
├── .env.example
└── README.md
```

## 系统监控接口（8.7）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/v1/monitor/token-usage` | Token 消耗统计（按用户/模型/时间） |
| GET | `/api/v1/monitor/api-stats` | API 调用量与响应时间 |
| GET | `/api/v1/monitor/error-logs` | 错误日志分页查询 |
| GET | `/api/v1/monitor/health` | 系统健康检查（免认证） |

开发文档为本地维护，不包含在公开仓库中。
