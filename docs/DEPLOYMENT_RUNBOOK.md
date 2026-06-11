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

---

## 9. 监控体系

### 9.1 健康检查端点

| 端点 | 认证 | 用途 |
| ---- | ---- | ---- |
| `GET /api/v1/health` | 否 | 负载均衡探活 |
| `GET /api/v1/monitor/health` | 否 | DB + Redis + 向量库组件状态 |

```bash
# 定时探活（建议 crontab 每 30 秒）
curl -sf http://localhost/api/v1/monitor/health | jq -e '.data.status != "unhealthy"'
```

**状态说明**：

| status | 含义 | 动作 |
| ------ | ---- | ---- |
| `healthy` | 全部组件正常 | 无需处理 |
| `degraded` | 单项组件异常 | 查看 `components` 详情，计划修复 |
| `unhealthy` | 关键组件不可用 | 立即告警，执行故障预案 |

### 9.2 Prometheus 指标

启用方式：`.env` 中设置 `PROMETHEUS_ENABLED=true`，重启 backend。

```bash
curl -s http://localhost:8000/metrics | head -20
```

**关键指标**：

| 指标名 | 类型 | 说明 |
| ------ | ---- | ---- |
| `http_requests_total` | Counter | 按路由统计请求量 |
| `http_request_duration_seconds` | Histogram | 接口响应时间分布 |
| `rag_retrieval_duration_seconds` | Histogram | RAG 检索耗时 |
| `process_resident_memory_bytes` | Gauge | 进程内存 |

### 9.3 Grafana Dashboard（推荐）

1. 部署 Grafana（可与 Prometheus 同 compose 网络）
2. 添加 Prometheus 数据源：`http://backend:8000/metrics`（经 Nginx 代理则为 `/metrics`）
3. 导入面板关注：
   - API P95/P99 响应时间
   - 错误率（5xx / 4xx）
   - RAG 检索延迟
   - Token 消耗趋势（亦可查应用内监控面板）

### 9.4 应用内监控

登录后访问 **监控面板**（`/monitor`）：

- Token 消耗统计与排行榜
- 接口调用量 / 响应时间趋势
- 错误日志查询与导出
- DAU / WAU / MAU 用户活跃度

### 9.5 日志采集

| 来源 | 路径 / 命令 | 保留建议 |
| ---- | ----------- | -------- |
| backend | `docker compose logs -f backend` | 90 天 |
| arq-worker | `docker compose logs -f arq-worker` | 30 天 |
| nginx | 容器内 `/var/log/nginx/access.log` | 30 天 |
| 审计日志 | 应用内「审计日志」+ DB `audit_logs` 表 | ≥ 90 天 |

**建议**：生产环境接入 ELK / Loki 集中采集，按 `tenant_id`、`trace_id` 建立索引。

### 9.6 告警规则（示例）

| 告警名 | 条件 | 级别 | 通知渠道 |
| ------ | ---- | ---- | -------- |
| API 高错误率 | 5xx 率 > 5% 持续 5 min | P1 | 企业微信 / 邮件 |
| 检索慢查询 | RAG P95 > 2 s 持续 10 min | P2 | 邮件 |
| 健康检查失败 | `/monitor/health` 非 200 连续 3 次 | P0 | 电话 + 企业微信 |
| Redis 不可用 | health components.redis = down | P0 | 电话 |
| 磁盘使用率高 | 数据卷 > 85% | P1 | 邮件 |
| Token 配额耗尽 | 租户配额使用 > 95% | P2 | 租户管理员邮件 |

---

## 10. 故障预案

### 10.1 响应等级与 SLA

| 级别 | 定义 | 响应时间 | 恢复目标 (RTO) |
| ---- | ---- | -------- | -------------- |
| P0 | 全站不可用 / 数据泄露 | 15 分钟 | 4 小时 |
| P1 | 核心功能受损（RAG/Agent/工作流） | 1 小时 | 8 小时 |
| P2 | 非核心功能异常 | 4 小时 | 24 小时 |
| P3 | 体验问题 / 单用户 | 下一工作日 | 72 小时 |

### 10.2 P0 — 全站不可用

**现象**：健康检查失败，用户无法登录。

**排查步骤**：

```bash
docker compose ps                    # 确认 6 容器均为 running
docker compose logs backend --tail 50
docker compose logs postgres --tail 20
curl -v http://localhost/api/v1/monitor/health
```

**常见原因与处理**：

| 原因 | 处理 |
| ---- | ---- |
| postgres 未启动 | `docker compose up -d postgres`，等待就绪后重启 backend |
| 数据库连接池耗尽 | 重启 backend；调大 `pool_size`；排查慢查询 |
| 磁盘满 | 清理日志与临时文件；扩容卷 |
| JWT_SECRET_KEY 变更 | 所有用户需重新登录；回滚配置 |

**升级指挥**：通知业务方 → 启用维护页（Nginx 503）→ 修复 → 验证健康检查 → 取消维护页。

### 10.3 P1 — RAG 检索/问答失败

**现象**：文档已解析，检索返回空或 500；问答 SSE 中断。

```bash
docker compose ps arq-worker
docker compose logs arq-worker --tail 30
docker compose exec backend ls -la /app/uploads/chroma
```

| 原因 | 处理 |
| ---- | ---- |
| arq-worker 停止 | `docker compose restart arq-worker` |
| Chroma 卷损坏 | 从备份恢复 `chroma_data` 卷；或触发知识库全量重建 |
| Embedding API 限流 | 检查用户 API Key 配额；切换备用模型 |
| 向量未入库 | 对知识库执行「全量重建」 |

### 10.4 P1 — Agent / 工作流执行失败

| 原因 | 处理 |
| ---- | ---- |
| LLM API Key 无效 | 用户在设置中更新 Key 并测试 |
| Redis Checkpoint 丢失 | 检查 redis 容器；工作流实例需重新执行 |
| Python 沙箱超时 | 审查用户代码；调大 `PYTHON_REPL_TIMEOUT` |
| 工作流图非法 | 使用 validate-graph API 校验后修复 |

```bash
docker compose logs backend | grep -i "workflow\|agent" | tail -30
docker compose exec redis redis-cli ping
```

### 10.5 P1 — 性能劣化（100+ 并发卡顿）

```bash
# 执行压测复现
pip install -r tests/perf/requirements.txt
locust -f tests/perf/locustfile.py --host=http://localhost \
  --users 100 --spawn-rate 10 --run-time 3m --headless
```

| 原因 | 处理 |
| ---- | ---- |
| 单实例 backend | 水平扩展 backend 副本 + Nginx 负载均衡 |
| 慢 SQL | 检查 `pg_stat_statements`；添加索引 |
| Chroma 内存过大 | 切换 Pinecone；或分知识库拆索引 |
| 未启用连接池 | 确认 Redis / DB 连接复用 |

### 10.6 P2 — 登录与安全事件

| 现象 | 处理 |
| ---- | ---- |
| 暴力破解 | Redis 自动锁定 15 min；检查审计日志 IP |
| 提示词注入攻击 | guardrails 模块拦截；复查审计日志 |
| Token 泄露 | 强制用户登出（黑名单）；轮换 JWT_SECRET_KEY |

```bash
docker compose exec redis redis-cli KEYS "login_fail:*"
# 查看审计日志
curl -H "Authorization: Bearer $TOKEN" \
  "http://localhost/api/v1/audit-logs?page=1&page_size=20"
```

### 10.7 数据恢复预案

| 场景 | RPO | 恢复步骤 |
| ---- | --- | -------- |
| PostgreSQL 误删 | ≤ 24 h | `pg_restore` 最近 `pg_dump` 备份 |
| 上传文件丢失 | ≤ 24 h | 恢复 `upload_data` 卷 |
| 向量库损坏 | ≤ 24 h | 恢复 `chroma_data` 或全量重建 |
| Redis 数据丢失 | Checkpoint 可丢 | 重启 redis；工作流需重新执行 |

**定期演练**：每季度执行一次备份恢复演练，记录 RTO 实测值。

### 10.8 联络清单（模板）

| 角色 | 职责 | 联系方式 |
| ---- | ---- | -------- |
| 值班运维 | 首响 P0/P1 | oncall@company.com |
| 后端负责人 | 服务修复 | — |
| DBA | 数据库恢复 | — |
| 安全负责人 | 安全事件 | security@company.com |
| 业务联系人 | 对外沟通 | — |

---

## 11. 性能基线与压测

发版前建议执行标准压测并归档报告（`docs/reports/PERF_REPORT.md`）：

```bash
locust -f tests/perf/locustfile.py --host=http://localhost \
  --users 100 --spawn-rate 10 --run-time 5m --headless \
  --csv=tests/perf/results/perf
```

验收标准：P95 ≤ 2 s，失败率 < 1%，100 并发无明显卡顿。
