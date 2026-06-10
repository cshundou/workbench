# AI Workbench

企业智能协作工作台 — 基于增强 RAG + 多 Agent + LangGraph 工作流。

技术栈：Vue 3 + FastAPI + PostgreSQL 16 + Redis 7。

## 前置要求

- [Docker](https://docs.docker.com/get-docker/) 25.x + [Docker Compose](https://docs.docker.com/compose/) 2.x
- 本地手动开发额外需要：
  - Node.js 20+、pnpm / npm
  - Python 3.11+
  - PostgreSQL 16、Redis 7

## 快速开始（Docker Compose）

### 1. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env`，至少配置以下密钥（按需）：

| 变量 | 说明 |
|------|------|
| `JWT_SECRET_KEY` | JWT 签名密钥（必填，生产环境请使用强随机值） |
| `OPENAI_API_KEY` | OpenAI / GPT-4o |
| `COHERE_API_KEY` | RAG 重排序 |
| `TAVILY_API_KEY` | Agent 联网搜索 |
| `DASHSCOPE_API_KEY` | 通义千问 |
| `VOLCENGINE_API_KEY` | 豆包 |
| `PINECONE_API_KEY` | 线上向量库（可选） |
| `LANGSMITH_API_KEY` | 链路追踪（可选） |

### 2. 启动所有服务

```bash
docker compose up --build
```

后台运行：

```bash
docker compose up -d --build
```

### 3. 验证

| 服务 | 地址 |
|------|------|
| 前端 | http://localhost:5173 |
| 后端 API 文档 | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 4. 常用命令

```bash
# 查看日志
docker compose logs -f backend

# 停止服务
docker compose down

# 停止并清除数据卷（会删除数据库数据）
docker compose down -v
```

### 服务依赖关系

```
postgres ──┐
           ├── backend ── frontend
redis   ───┘
```

- `backend` 等待 `postgres`、`redis` 健康检查通过后启动
- `frontend` 依赖 `backend` 启动

Docker 网络内服务互通：

- 数据库：`postgres:5432`
- 缓存：`redis:6379`
- 后端：`backend:8000`

## 本地手动开发

适合需要热重载、断点调试的场景。先启动基础设施，再分别运行前后端。

### 1. 启动 PostgreSQL 和 Redis

仅启动数据库与缓存：

```bash
docker compose up -d postgres redis
```

或在本机安装并启动 PostgreSQL 16、Redis 7。

### 2. 配置本地环境变量

```bash
cp .env.example .env
```

将 `.env` 中的连接地址改为本机：

```env
DATABASE_URL=postgresql+asyncpg://ai_workbench:ai_workbench_secret@localhost:5432/ai_workbench
REDIS_URL=redis://localhost:6379/0
POSTGRES_HOST=localhost
REDIS_HOST=localhost
VITE_API_BASE_URL=/api/v1
VITE_API_PROXY_TARGET=http://localhost:8000
```

### 3. 后端

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 数据库迁移（首次或模型变更后）
alembic upgrade head

# 启动开发服务器
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 4. 前端

```bash
cd frontend
pnpm install   # 或 npm install
pnpm dev       # 或 npm run dev
```

访问 http://localhost:5173 。

## Stage 6：Nginx 反向代理

生产部署时启用 Nginx，统一入口：

1. 编辑 `docker-compose.yml`，取消 `nginx` 服务注释
2. 配置文件位于 `nginx/nginx.conf`
3. 启动后通过 http://localhost:80 访问

```bash
docker compose up -d --build
```

路由规则：

- `/api/*`、`/docs` → 后端 `backend:8000`
- `/api/v1/stream/*` → SSE 流式代理（关闭缓冲）
- `/` → 前端 `frontend:5173`

## 项目结构

```
ai-workbench/
├── backend/           # FastAPI 后端
├── frontend/          # Vue 3 前端
├── docs/              # 开发文档
├── nginx/             # Nginx 配置（Stage 6）
├── docker-compose.yml
├── .env.example
└── README.md
```

详细开发规范见 [docs/DEVELOPMENT_DOCUMENT.md](docs/DEVELOPMENT_DOCUMENT.md)。

## 常见问题

**`docker compose up` 提示找不到 Dockerfile**

确保 `backend/Dockerfile` 与 `frontend/Dockerfile` 已按项目脚手架生成（见开发文档第 9.1 节）。

**后端无法连接数据库**

- Docker 模式：确认 `DATABASE_URL` 使用主机名 `postgres`
- 本地模式：确认 `DATABASE_URL` 使用 `localhost`，且 PostgreSQL 已启动

**前端请求 API 跨域失败**

检查 `.env` 中 `CORS_ORIGINS` 是否包含前端地址（默认 `http://localhost:5173`）。
