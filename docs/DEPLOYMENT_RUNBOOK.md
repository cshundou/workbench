# AI Workbench 部署 Runbook

**版本**：v1.0  
**更新日期**：2026-06-11  
**适用环境**：开发 / 测试 / 生产（Docker Compose）

---

## 1. 环境要求

| 组件 | 最低版本 |
| ---- | -------- |
| Docker | 24+ |
| Docker Compose | v2.20+ |
| 可用内存 | 8 GB（含 Chroma + PostgreSQL） |
| 磁盘 | 20 GB |

---

## 2. 环境变量清单

复制 `.env.example` 为 `.env`，关键变量：

| 变量 | 必填 | 说明 |
| ---- | ---- | ---- |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | 是 | 数据库凭据 |
| `DATABASE_URL` | 是 | 异步连接串（compose 内自动注入） |
| `REDIS_URL` | 是 | Redis 连接 |
| `JWT_SECRET_KEY` | 是 | JWT 签名密钥（生产必须更换） |
| `ENCRYPTION_SECRET_KEY` | 是 | API Key AES 加密主密钥 |
| `VECTOR_STORE` | 否 | `chroma`（默认）或 `pinecone` |
| `LANGCHAIN_TRACING_V2` | 否 | `true` 启用 LangSmith |
| `LANGCHAIN_API_KEY` | 否 | LangSmith Key |
| `PROMETHEUS_ENABLED` | 否 | `true` 暴露 `/metrics` |
| `PYTHON_REPL_MODE` | 否 | `local` 或 `docker`（生产推荐 docker） |
| `SQL_TOOL_ALLOWED_TABLES` | 否 | 逗号分隔表白名单 |

---

## 3. 首次部署步骤

```bash
# 1. 克隆并进入项目
cd ai-workbench

# 2. 配置环境变量
cp .env.example .env
# 编辑 .env，至少设置 JWT_SECRET_KEY 与 ENCRYPTION_SECRET_KEY

# 3. 启动全部服务（含 arq-worker）
docker compose up -d

# 4. 数据库迁移
docker compose exec backend alembic upgrade head

# 5. 验证健康检查
curl http://localhost/api/v1/monitor/health
```

**服务拓扑（6 容器）**：

| 容器 | 端口 | 职责 |
| ---- | ---- | ---- |
| postgres | 5432 | 主数据库 |
| redis | 6379 | 缓存 / 队列 / Checkpoint |
| backend | 8000 | FastAPI API |
| arq-worker | — | 文档解析 / 工作流异步任务 |
| frontend | 5173 | Vue 开发服务 |
| nginx | 80 | 反向代理入口 |

---

## 4. 健康检查

```bash
curl -s http://localhost/api/v1/monitor/health | jq
```

预期：`status` 为 `healthy` 或 `degraded`（仅一项组件异常）。

---

## 5. 常见故障排查

| 现象 | 原因 | 处理 |
| ---- | ---- | ---- |
| 文档一直「等待解析」 | arq-worker 未启动 | `docker compose ps arq-worker`，重启 worker |
| 401 登录失败 | 数据库未迁移 / 无初始用户 | `alembic upgrade head`，检查 users 表 |
| RAG 问答 428 | 未配置 LLM API Key | 设置 → API 密钥管理 |
| Redis 连接失败 | redis 容器未就绪 | `docker compose logs redis` |
| Chroma 权限错误 | 卷挂载权限 | `chown` uploads/chroma 目录 |

---

## 6. 升级与回滚

```bash
# 升级
git pull
docker compose build
docker compose up -d
docker compose exec backend alembic upgrade head

# 回滚迁移（谨慎）
docker compose exec backend alembic downgrade -1
```

---

## 7. 备份策略

- **PostgreSQL**：`docker compose exec postgres pg_dump -U ai_workbench ai_workbench > backup.sql`
- **上传文件**：备份 `upload_data` Docker 卷
- **Chroma 向量**：备份 `chroma_data` Docker 卷

---

## 8. 外部依赖配置

- **Pinecone**：`VECTOR_STORE=pinecone` + 用户 BYOK Pinecone Key
- **LangSmith**：`LANGCHAIN_TRACING_V2=true` + `LANGCHAIN_API_KEY`
- **LLM**：用户在「设置 > API 密钥」配置 OpenAI / 兼容端点 Key
