# 企业智能协作工作台 — 三期开发文档

**文档版本**：v3.0-draft  
**编制日期**：2026-06-11  
**前置基线**：二期功能实现（`docs/PHASE2_DEVELOPMENT_DOCUMENT.md` v2.0-draft）  
**主文档**：`docs/DEVELOPMENT_DOCUMENT.md` v1.0  
**适用对象**：前端开发者、后端 / AI 开发者、全栈开发者、运维工程师、测试工程师

---

## 一、二期交付现状摘要

> 本节基于 2026-06-11 代码审计结果，反映二期开发完成后的实际状态。

### 1.1 已实现功能清单

| 模块 | 功能点 | 实现状态 | 主要路径 |
| ---- | ------ | -------- | -------- |
| **账户 & 权限** | JWT 登录 / 登出 / 获取用户信息 | ✅ | `backend/app/api/v1/auth.py` |
| | RBAC 角色权限（含 tenant/audit/task） | ✅ | `backend/app/core/permissions.py` |
| | 多租户数据隔离（tenant_id） | ✅ | 各 Service 层 |
| | 用户 / 角色 CRUD | ✅ | `users.py`, `roles.py` + 前端 Settings |
| | 租户 CRUD（超管） | ✅ | `tenants.py` + `TenantManagement.vue` |
| | 审计日志（登录 / CRUD / 工作流执行） | ✅ | `audit_service.py` + `AuditLogs.vue` |
| | 用户自管 API Key（LLM/Tavily/Cohere/Pinecone BYOK） | ✅ | `user_api_keys.py` |
| | Refresh Token / 登出黑名单 | ❌ | 仍为无状态 JWT |
| **增强 RAG** | 知识库 CRUD + 权限 | ✅ | `knowledge_bases.py` |
| | 多格式文档上传（PDF/TXT/MD/DOCX/XLSX/HTML/PPT/PPTX） | ✅ | `document_loader.py` |
| | 7 层 RAG 链路（分块/混合检索/重排/引用） | ✅ | `backend/app/services/rag/` |
| | KB `chunk_size` / `chunk_overlap` 配置生效 | ✅ | `chunker.py`, `rag_service.py` |
| | 文档解析进度 Redis 持久化 | ✅ | `parse_progress:{doc_id}` |
| | 向量全量 / 增量更新 | ✅ | `rag_service.py` |
| | RAG 流式问答 + 引用标注 | ✅ | `knowledge/Chat.vue` |
| | RAG / 纯 LLM 模式切换（use_rag） | ✅ | 前后端均已支持 |
| | 文档在线预览（PDF/Word/Excel） | ✅ | `DocumentPreview.vue` |
| | 检索统计 + 优化建议 | ✅ | API + 详情页「检索分析」Tab |
| | Pinecone 向量库切换 | ✅ | `vector_store.py` + BYOK |
| | 网页 URL 导入 | ❌ | — |
| | 异步任务队列（arq） | ⚠️ 部分 | 代码已接入，docker-compose 无 worker |
| **单 Agent** | 智能体 CRUD / 复制 | ✅ | `agents.py` |
| | Monaco Editor 提示词编辑 | ✅ | `PromptEditor.vue` |
| | 4 种内置工具（KB/Tavily/Python/SQL） | ✅ | `agent/tools/` |
| | 流式对话 + 工具可视化 + 中断 | ✅ | `agents/Chat.vue` |
| | 对话历史持久化 + 会话 UI | ✅ | `ChatHistory` + 左侧会话栏 |
| | calculator / web_scraper 扩展工具 | ❌ | — |
| | 租户级工具启用开关 | ❌ | — |
| **LangGraph 工作流** | 标准五 Agent 拓扑执行 | ✅ | `graph_builder.py` |
| | 自定义 graph_definition 运行时执行 | ✅ | `build_from_definition()` |
| | 可视化编辑器 | ✅ | `workflows/Edit.vue` |
| | 人工介入节点 | ✅ | `workflow_service.py` |
| | Redis Checkpoint | ✅ | `redis_saver.py` |
| | WebSocket 实时节点状态 | ✅ | `workflow_ws.py` |
| | 执行 Agent 真实工具调用 | ✅ | PythonRepl / SqlQuery |
| | 执行历史 + 重跑 | ✅ | `workflows/History.vue` |
| | 图校验 REST API | ❌ | 仅 Service 层 `validate_graph_definition()` |
| | 工作流发布 / 草稿状态 | ❌ | — |
| **流式交互** | SSE（RAG）+ Fetch Stream（Agent）+ WebSocket（工作流） | ✅ | `sse.ts`, `agent.ts`, `graph.ts` |
| | Markdown / 代码块渲染 | ✅ | `StreamingText.vue` |
| **系统监控** | Token 消耗 / API 调用 / 响应时间 / 错误日志 | ✅ | `monitor/Dashboard.vue` |
| | 健康检查 | ✅ | DB + Redis |
| | 用户活跃度（DAU/WAU/MAU） | ✅ | `/monitor/user-activity` |
| | LangSmith 链路追踪 | ⚠️ 部分 | 后端环境变量支持，前端无 trace 跳转 |
| | Prometheus + Grafana | ❌ | — |
| | Token 配额 / 限流可视化 | ❌ | 租户表有字段，未落地运行时 |
| **部署 & 工程** | Docker Compose + Nginx | ✅ | `docker-compose.yml` |
| | GitHub Actions CI（pytest + lint + build） | ✅ | `.github/workflows/ci.yml` |
| | Husky pre-commit | ✅ | `frontend/.husky/pre-commit` |
| | 后端单元测试（14 文件） | ⚠️ 部分 | 覆盖率未达 70% 门禁 |
| | 后端集成 / E2E 测试 | ⚠️ 极弱 | 仅 health / 401 两条用例 |
| | 前端 Vitest | ❌ | 依赖已装，无 `.spec.ts` |
| | Playwright E2E | ❌ | — |
| | 部署 Runbook | ❌ | 第 11 章仅数行占位 |
| | 开发文档 8.4~11 章正文 | ⚠️ 极简 | 接口 / 测试 / 部署未详述 |

### 1.2 二期验收检查表对照

#### 8.1 功能验收（15 项）

| # | 验收项 | 状态 |
| - | ------ | ---- |
| 1 | 上传 PPT 并成功检索 | ✅ |
| 2 | KB 分块参数修改后重新入库生效 | ✅ |
| 3 | 文档解析进度在服务重启后仍可查询 | ✅ |
| 4 | Agent 提示词 Monaco 编辑保存正常 | ✅ |
| 5 | Agent 可查看 / 切换历史会话 | ✅ |
| 6 | 知识库 Chat 可切换纯 LLM / RAG 模式 | ✅ |
| 7 | 文档 PDF/Word/Excel 在线预览 | ✅ |
| 8 | 工作流可视化编辑并保存 | ✅ |
| 9 | 自定义工作流拓扑可执行完成 | ✅ |
| 10 | 执行 Agent 真实调用 Python/SQL 工具 | ✅ |
| 11 | 工作流执行历史查看与重跑 | ✅ |
| 12 | 检索分析图表展示 | ✅ |
| 13 | 监控面板展示 DAU/MAU | ✅ |
| 14 | LangSmith 可查看 trace（配置后） | ⚠️ 后端可上报，前端无入口 |
| 15 | Pinecone 模式切换可用（配置后） | ⚠️ 后端已实现，需环境验证 |

**功能验收通过率：12/15 完全通过，2/15 部分通过，1/15 未实现（URL 导入不在二期清单但为 P1 残留）。**

#### 8.2 工程验收（6 项）

| # | 验收项 | 状态 |
| - | ------ | ---- |
| 1 | pytest 覆盖率 ≥ 70% | ❌ |
| 2 | 前端 Vitest 核心 Store / 组件测试通过 | ❌ |
| 3 | Playwright E2E 4 条主路径通过 | ❌ |
| 4 | GitHub Actions CI 绿灯 | ⚠️ 基础流水线有，无覆盖率门禁 |
| 5 | docker compose up 全新环境 15 分钟内可用 | ⚠️ 可启动，缺 arq-worker |
| 6 | 部署 Runbook 文档完整 | ❌ |

**工程验收通过率：0/6 完全通过。**

#### 8.3 安全验收（4 项）

| # | 验收项 | 状态 |
| - | ------ | ---- |
| 1 | 审计日志记录关键操作 | ✅ |
| 2 | 租户间数据隔离渗透测试通过 | ⚠️ 逻辑已实现，未做正式测试 |
| 3 | PythonREPL 沙箱无法执行危险 import | ⚠️ 进程内 AST 校验，非容器隔离 |
| 4 | SQL 工具仅允许 SELECT | ✅ |

**安全验收通过率：1/4 完全通过，3/4 部分通过。**

### 1.3 与主开发文档符合度评估

| 维度 | 符合度 | 说明 |
| ---- | ------ | ---- |
| 技术栈主体 | **92%** | Vue3/Pinia/FastAPI/LangChain/LangGraph/PostgreSQL/Redis/Chroma/Pinecone/arq 已落地 |
| 数据库表结构 | **95%** | 与文档 4.2 一致，额外增加 `user_api_keys`、`audit_logs` |
| 第 6 章功能模块 | **88%** | 核心链路齐全，缺 URL 导入、工作流发布等 |
| 第 7 章前端规范 | **80%** | Monaco/预览/会话/编辑器已实现 |
| 第 8 章 API 文档 | **40%** | 代码接口远多于文档描述 |
| 第 10 章测试 | **25%** | 有测试骨架，远未达企业门禁 |
| 第 11 章部署 | **55%** | docker-compose 可用，缺 worker 与 Runbook |
| 开发文档自身完整性 | **45%** | 第 8.4~11 章、第 14 章仍为占位 |

**结论：二期达到「功能可内测 / 技术演示」标准，尚未达到二期文档定义的「企业级正式交付」标准。工程质量与安全加固是主要缺口。**

---

## 二、二期未达标项（三期必须补齐）

### 2.1 P0 — 阻塞正式交付

| 编号 | 缺口 | 文档依据 | 影响 |
| ---- | ---- | -------- | ---- |
| P0-01 | 后端测试覆盖率 < 70%，集成 / E2E 几乎为空 | 二期 8.2 / 主文档第 10 章 | 无法保证回归，不符合企业交付门禁 |
| P0-02 | 无 Playwright E2E 主路径测试 | 二期 4.1.1 | 关键用户链路无自动化保障 |
| P0-03 | docker-compose 缺少 arq-worker 服务 | 二期 4.6.2 | 文档解析 / 工作流异步任务无法在生产 compose 环境运行 |
| P0-04 | `DEVELOPMENT_DOCUMENT.md` 第 8~11 章正文缺失 | 二期 4.1.2 / P1-12 | 交付文档不完整，运维 / 联调无据可依 |
| P0-05 | 无独立部署 Runbook | 二期 8.2 | 生产部署与故障排查缺乏标准流程 |

### 2.2 P1 — 二期功能残留

| 编号 | 缺口 | 文档依据 |
| ---- | ---- | -------- |
| P1-01 | RAG 网页 URL 导入 | 二期 4.2.2 |
| P1-02 | 工作流图校验 REST API | 二期 4.4.1 / 五章 API 清单 |
| P1-03 | 工作流重跑专用 API（当前前端直接调 execute） | 二期 4.4.4 |
| P1-04 | LangSmith trace 前端跳转入口 | 二期 4.5.2 |
| P1-05 | 前端 Vitest 组件 / Store 单测 | 二期 4.1.1 |
| P1-06 | CI 覆盖率门禁与 PR 阻断规则 | 二期 4.1.1 |
| P1-07 | Agent 工具扩展（calculator / web_scraper） | 二期 4.3.3 |

### 2.3 P2 — 企业生产化增强

| 编号 | 缺口 | 说明 |
| ---- | ---- | ---- |
| P2-01 | Refresh Token + JWT 登出黑名单 | 二期 2.3 P2-07 |
| P2-02 | Token 配额 / 限流可视化 | 租户 `monthly_token_limit` 字段已有，运行时未 enforcement |
| P2-03 | PythonREPL Docker 容器沙箱 | 当前为进程内 AST 校验，不满足生产安全 |
| P2-04 | SQL 工具只读副本 + 表白名单 | 二期 2.3 P2-06 |
| P2-05 | Prometheus 指标 + Grafana Dashboard | 二期 2.3 P2-08 |
| P2-06 | 租户级工具启用开关 | 二期 4.3.3 |
| P2-07 | 工作流发布 / 草稿状态管理 | 主文档 6.4 |
| P2-08 | 暗色主题 + i18n（中/英） | 二期 2.3 P2-09 |
| P2-09 | 检索质量评估（召回率 / 准确率采样标注） | 主文档 5.1.2 |
| P2-10 | 多实例水平扩展验证 | Redis 进度 / Checkpoint 共享一致性 |

---

## 三、三期总体目标

**目标定位**：补齐二期工程与安全验收缺口，完善文档与运维体系，达到可对外正式交付的企业级标准。

**交付标准（三期验收）**：

1. 主文档第 6 章全部功能点实现率 ≥ **98%**
2. 后端核心模块单元测试覆盖率 ≥ **70%**（CI 强制门禁）
3. Playwright E2E **4 条主路径**全部通过（CI main 分支）
4. 前端 Vitest 核心 Store + 关键组件测试 ≥ **15 个用例**
5. `docker compose up` 含 **backend + frontend + nginx + postgres + redis + arq-worker**，15 分钟内可用
6. 独立《部署 Runbook》+ 主文档第 8~11 章正文补全
7. 无 P0 级已知缺陷；P1 项全部关闭
8. 安全验收 4 项全部通过（含正式租户隔离测试报告）

---

## 四、三期功能需求详述

### 4.1 测试体系完善（P0）

#### 4.1.1 后端测试目录规划

```
backend/tests/
├── conftest.py                    # 已有：异步 DB fixture、测试客户端
├── unit/
│   ├── test_auth.py               # ✅ 已有
│   ├── test_permissions.py        # ✅ 已有
│   ├── test_rag_chunker.py        # ✅ 已有
│   ├── test_rag_retriever.py      # ✅ 已有
│   ├── test_rag_parse_progress.py # ✅ 已有
│   ├── test_rag_service.py        # ✅ 已有，需扩展
│   ├── test_agent_tools.py        # ✅ 已有
│   ├── test_workflow_graph.py     # ✅ 已有
│   ├── test_core_modules.py       # ✅ 已有
│   ├── test_tenant_service.py     # 🆕 租户 CRUD + 配额
│   ├── test_audit_service.py      # 🆕 审计写入 / 查询
│   ├── test_task_queue.py         # 🆕 arq 入队 / 状态
│   └── test_auth_refresh.py       # 🆕 Refresh Token（P2 同步）
├── integration/
│   ├── test_knowledge_api.py      # ✅ 已有，需扩展 CRUD + chat mock
│   ├── test_agent_api.py          # 🆕 智能体 CRUD + 历史
│   ├── test_workflow_api.py       # 🆕 执行 + validate-graph
│   ├── test_tenant_api.py         # 🆕 租户隔离
│   └── test_audit_api.py          # 🆕 审计日志查询
└── e2e/
    └── test_full_pipeline.py      # 🆕 登录→RAG→Agent→Workflow 串联
```

**Mock LLM 策略**：

- 单元测试：mock `ChatOpenAI` / `UserKeyContext`，不发起真实 API 调用
- 集成测试：使用 `pytest-recording` 或固定 fixture 响应
- E2E：Playwright 侧使用 mock server 或 recorded responses

**覆盖率门禁**：

```yaml
# .github/workflows/ci.yml 增量
- name: Run pytest with coverage gate
  working-directory: backend
  run: pytest tests/ -q --cov=app --cov-fail-under=70
```

#### 4.1.2 前端 Vitest 规划

```
frontend/src/
├── stores/
│   ├── user.spec.ts           # 登录态、权限判断
│   ├── rag.spec.ts            # 知识库列表、文档状态
│   ├── agent.spec.ts          # 会话加载
│   └── graph.spec.ts          # 工作流节点状态
├── components/
│   ├── agent/PromptEditor.spec.ts
│   ├── knowledge/DocumentPreview.spec.ts
│   └── workflow/WorkflowCanvas.spec.ts
└── utils/
    └── sse.spec.ts            # SSE 解析
```

**package.json 增量脚本**：

```json
{
  "scripts": {
    "test:unit": "vitest run",
    "test:unit:watch": "vitest",
    "test:e2e": "playwright test"
  }
}
```

#### 4.1.3 Playwright E2E 场景

```
frontend/e2e/
├── fixtures/
│   └── auth.ts                # 登录 fixture
├── login.spec.ts              # 登录 / 登出 / 权限跳转
├── rag-chat.spec.ts           # 上传文档 → RAG 问答 → 引用展示
├── agent-chat.spec.ts         # 创建 Agent → 对话 → 工具调用展示
└── workflow-execute.spec.ts   # 编辑工作流 → 执行 → 历史重跑
```

**CI 策略**：

- PR：lint → backend unit → backend integration → frontend unit → build
- main：额外 Playwright E2E（mock LLM）

---

### 4.2 运维与部署完善（P0）

#### 4.2.1 docker-compose 增加 arq-worker

```yaml
# docker-compose.yml 增量
  arq-worker:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: ai-workbench-arq-worker
    restart: unless-stopped
    env_file:
      - .env
    environment:
      DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      REDIS_URL: redis://redis:6379/${REDIS_DB:-0}
    command: arq app.worker.WorkerSettings
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./backend:/app
      - chroma_data:/app/chroma_data
      - upload_data:/app/uploads
    networks:
      - ai-workbench-network
```

**验收**：上传大文档后，backend 重启，解析任务仍由 worker 完成；`GET /tasks/{task_id}` 可查询状态。

#### 4.2.2 部署 Runbook（独立文档）

新建 `docs/DEPLOYMENT_RUNBOOK.md`，至少包含：

| 章节 | 内容 |
| ---- | ---- |
| 1. 环境要求 | OS、Docker、Node、Python 版本 |
| 2. 环境变量清单 | `.env.example` 全字段说明 |
| 3. 首次部署步骤 | compose up → alembic upgrade → 初始化超管 |
| 4. 服务拓扑 | 6 容器职责与端口 |
| 5. 健康检查 | `/api/v1/monitor/health` 预期响应 |
| 6. 常见故障 | DB 连接失败、Redis 超时、arq 任务堆积、Chroma 权限 |
| 7. 升级与回滚 | alembic downgrade、镜像 tag 策略 |
| 8. 外部依赖 | Pinecone / LangSmith / LLM Key 配置 |
| 9. 备份策略 | PostgreSQL dump、uploads 卷、Chroma 数据 |

#### 4.2.3 主文档补全规范

修订 `docs/DEVELOPMENT_DOCUMENT.md`：

| 章节 | 补全要求 |
| ---- | -------- |
| 8.4 智能体管理接口 | 全部 CRUD + chat + history + delete session，含请求/响应示例 |
| 8.5 工作流管理接口 | execute / intervene / validate-graph / replay / executions |
| 8.6 流式交互接口 | SSE 事件类型、Agent stream chunk 格式、WebSocket 消息协议 |
| 8.7 系统监控接口 | token-usage / api-stats / error-logs / user-activity |
| 8.8 租户与审计接口 | tenants CRUD / audit-logs / tasks |
| 第 9 章 | 标注一/二/三期里程碑与完成状态 |
| 第 10 章 | pytest / vitest / playwright 命令、目录、mock 策略 |
| 第 11 章 | 完整部署流程，引用 Runbook |
| 第 14 章 | 最佳实践、性能优化、常见问题正文 |

---

### 4.3 RAG 增强（P1）

#### 4.3.1 网页 URL 导入

**新增 API**

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/knowledge-bases/{kb_id}/import-url` | URL 抓取 → 清洗 → 入库 |

**请求体**

```json
{
  "url": "https://example.com/docs/guide",
  "title": "可选自定义标题",
  "auto_refresh": false
}
```

**实现要点**

- 使用 `httpx` 异步抓取，超时 30s，最大 5MB
- HTML 清洗：`BeautifulSoup` 提取正文，去除 script/style
- 入库流程复用现有 `document_loader` + `rag_service.ingest_document`
- 异步入队：`enqueue_task("parse_document_task", doc_id, ...)`
- 审计：`audit_service.record_crud_action(action="import_url", ...)`

**前端**：知识库详情页「导入链接」按钮 + URL 输入对话框

#### 4.3.2 检索质量评估（P2，可选三期 W5~W6）

**新增表 `rag_eval_samples`**

```sql
CREATE TABLE rag_eval_samples (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    kb_id INTEGER NOT NULL,
    query TEXT NOT NULL,
    expected_doc_ids INTEGER[],
    retrieved_doc_ids INTEGER[],
    hit BOOLEAN,
    created_by INTEGER,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**API**

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/knowledge-bases/{kb_id}/eval-samples` | 提交标注样本 |
| GET | `/knowledge-bases/{kb_id}/eval-metrics` | 召回率 / MRR |

---

### 4.4 Agent 增强（P1 / P2）

#### 4.4.1 工具市场扩展

**新增内置工具**

| 工具名 | 说明 | 依赖 |
| ------ | ---- | ---- |
| `calculator` | 安全数学表达式计算（AST 白名单） | 无外部 Key |
| `web_scraper` | 指定 URL 正文抓取（可选） | 无 / httpx |

**工具注册表扩展**（`agent/tools/__init__.py`）：

```python
AVAILABLE_TOOL_DEFINITIONS.append({
    "name": "calculator",
    "label": "计算器",
    "description": "执行数学表达式计算",
})
```

#### 4.4.2 租户级工具启用开关（P2）

**新增表 `tenant_tool_configs`**

```sql
CREATE TABLE tenant_tool_configs (
    id SERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    tool_name VARCHAR(64) NOT NULL,
    enabled BOOLEAN DEFAULT TRUE,
    UNIQUE (tenant_id, tool_name)
);
```

**逻辑**：`AgentService._build_tools()` 读取租户配置，禁用工具不注入 Agent。

**前端**：设置 → 工具管理（租户管理员）

---

### 4.5 LangGraph 工作流增强（P1 / P2）

#### 4.5.1 图校验 REST API

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| POST | `/workflows/{id}/validate-graph` | 校验 graph_definition 合法性 |

**请求体**（可选，不传则校验库内定义）：

```json
{
  "graph_definition": { "nodes": [...], "edges": [...] }
}
```

**响应**

```json
{
  "code": 200,
  "data": {
    "valid": true,
    "errors": [],
    "warnings": ["节点 knowledge_agent 未配置 kb_ids"]
  }
}
```

**实现**：复用 `GraphBuilder.validate_graph_definition()`，捕获异常转为 errors 列表。

**前端**：`WorkflowEdit.vue` 保存前自动调用校验，展示错误定位。

#### 4.5.2 重跑专用 API

| 方法 | 路径 | 说明 |
| ---- | ---- | ---- |
| GET | `/workflows/{id}/executions/{eid}/replay` | 获取历史执行 input_params |

**响应**

```json
{
  "code": 200,
  "data": {
    "execution_id": 42,
    "input_params": {
      "task": "分析 Q3 销售数据",
      "require_human_approval": true,
      "kb_id": 1,
      "extra_params": {}
    },
    "graph_definition_snapshot": { "nodes": [], "edges": [] }
  }
}
```

**说明**：前端 `History.vue` 改为先调 replay 获取参数，再调 execute；支持未来「按历史拓扑重跑」。

#### 4.5.3 工作流发布 / 草稿（P2）

**数据库增量**（`workflows` 表）：

```sql
ALTER TABLE workflows ADD COLUMN status VARCHAR(16) DEFAULT 'draft';
-- draft | published | archived
ALTER TABLE workflows ADD COLUMN published_at TIMESTAMPTZ;
```

**规则**：

- 仅 `published` 状态可被非管理员执行
- 编辑已发布工作流自动创建草稿副本或降级为 `draft`
- 前端列表展示状态 Tag + 「发布」按钮

---

### 4.6 系统监控与可观测性（P1 / P2）

#### 4.6.1 LangSmith 前端集成

**后端增量**：RAG / Agent / Workflow 响应 metadata 中返回 `langsmith_trace_id`（LangChain callback 提取）。

**前端增量**：

- 组件：`LangSmithTraceLink.vue`
- 展示位置：Agent 对话消息 footer、工作流执行详情、监控页「最近 trace」
- URL 模板：`https://smith.langchain.com/o/{org}/projects/p/{project}/r/{trace_id}`

**降级**：无 trace_id 或 Key 未配置时不渲染链接。

#### 4.6.2 Prometheus 指标（P2）

**依赖**：`prometheus-fastapi-instrumentator`

**暴露端点**：`GET /metrics`（仅内网 / 鉴权访问）

**核心指标**：

| 指标名 | 类型 | 说明 |
| ------ | ---- | ---- |
| `http_requests_total` | Counter | 按 path/method/status |
| `http_request_duration_seconds` | Histogram | 响应延迟 |
| `rag_retrieval_duration_seconds` | Histogram | RAG 检索耗时 |
| `llm_tokens_total` | Counter | 按 model/user 聚合 |
| `workflow_executions_total` | Counter | 按 status |
| `arq_queue_depth` | Gauge | 异步队列深度 |

**Grafana**：提供 `deploy/grafana/dashboard.json` 预置 Dashboard。

#### 4.6.3 Token 配额与限流（P2）

**运行时 enforcement**：

- 租户表已有 `monthly_token_limit`
- 新增 `tenant_token_usage` Redis key：`tenant:{id}:tokens:{YYYY-MM}`
- 每次 LLM 调用后累加，超限返回 `429 QuotaExceeded`
- 前端监控页 + 租户管理页展示用量进度条

---

### 4.7 安全增强（P2）

#### 4.7.1 Refresh Token + 登出黑名单

**流程**：

```
登录 → access_token (15min) + refresh_token (7d, HttpOnly Cookie 或 body)
刷新 → POST /auth/refresh { refresh_token } → 新 access_token
登出 → refresh_token 写入 Redis 黑名单 (TTL=剩余有效期)
```

**新增表**（可选，或使用 Redis）：

```sql
CREATE TABLE refresh_tokens (
    id BIGSERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    token_hash VARCHAR(128) NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

**前端**：axios 拦截器 401 时自动 refresh，refresh 失败跳转登录。

#### 4.7.2 PythonREPL Docker 沙箱

**方案**：

- 生产环境 `PYTHON_REPL_MODE=docker`
- 每次执行：`docker run --rm --network=none --memory=128m --cpus=0.5 python:3.11-slim`
- 代码通过 stdin 传入，stdout/stderr 捕获，超时 30s 强杀容器
- 开发 / 测试环境保持 `local` 模式（现有 AST 校验）

**配置**：

```env
PYTHON_REPL_MODE=local|docker
PYTHON_REPL_DOCKER_IMAGE=python:3.11-slim
PYTHON_REPL_TIMEOUT_SECONDS=30
```

#### 4.7.3 SQL 工具只读副本 + 表白名单

**配置**：

```env
SQL_TOOL_READONLY_DSN=postgresql+asyncpg://readonly:xxx@replica:5432/ai_workbench
SQL_TOOL_ALLOWED_TABLES=users,orders,products
```

**逻辑**：`SqlQueryTool` 连接只读 DSN；解析 SQL AST，仅允许 SELECT；表名必须在白名单内。

#### 4.7.4 租户隔离渗透测试

**测试用例**（集成测试 + 手工 checklist）：

- 租户 A 用户无法通过 ID 猜测访问租户 B 的知识库 / Agent / 工作流
- 跨租户 API 返回 404（非 403，避免信息泄露）
- WebSocket 工作流订阅需校验 execution 归属
- 审计日志不可跨租户查询

**交付物**：`docs/SECURITY_TEST_REPORT.md` 测试报告模板。

---

### 4.8 前端体验增强（P2）

#### 4.8.1 国际化（i18n）

**依赖**：`vue-i18n@9`

**范围**：Phase 3 覆盖框架 UI（Element Plus 已有 locale）；业务文案中英文各一套。

**目录**：

```
frontend/src/locales/
├── zh-CN.json
└── en-US.json
```

**入口**：`App.vue` 切换语言，持久化到 `localStorage`。

#### 4.8.2 暗色主题

- 基于 CSS 变量 + Element Plus dark css vars
- 切换组件：`ThemeSwitch.vue` 置于 `AppHeader`
- 持久化：`localStorage.theme = light|dark`
- Monaco Editor 同步切换 `vs` / `vs-dark`

---

## 五、三期 API 增量清单

| 模块 | 方法 | 路径 | 优先级 | 说明 |
| ---- | ---- | ---- | ------ | ---- |
| RAG | POST | `/knowledge-bases/{kb_id}/import-url` | P1 | URL 导入 |
| RAG | POST | `/knowledge-bases/{kb_id}/eval-samples` | P2 | 检索评估样本 |
| RAG | GET | `/knowledge-bases/{kb_id}/eval-metrics` | P2 | 检索评估指标 |
| Workflow | POST | `/workflows/{id}/validate-graph` | P1 | 校验图定义 |
| Workflow | GET | `/workflows/{id}/executions/{eid}/replay` | P1 | 获取重跑参数 |
| Workflow | POST | `/workflows/{id}/publish` | P2 | 发布工作流 |
| Auth | POST | `/auth/refresh` | P2 | 刷新 access_token |
| Monitor | GET | `/metrics` | P2 | Prometheus 指标 |
| Tenant | GET | `/tenants/{id}/quota-usage` | P2 | 租户 Token 用量 |
| Tool | GET | `/tools` | P2 | 可用工具列表 |
| Tool | PUT | `/tenants/{id}/tool-configs` | P2 | 租户工具开关 |

---

## 六、三期前端路由 / 组件增量

| 路径 / 组件 | 说明 | 优先级 |
| ----------- | ---- | ------ |
| `LangSmithTraceLink.vue` | trace 外链组件 | P1 |
| `frontend/e2e/*.spec.ts` | Playwright 场景 | P0 |
| `ThemeSwitch.vue` | 暗色主题切换 | P2 |
| `settings/ToolManagement.vue` | 租户工具开关 | P2 |
| `monitor/QuotaDashboard.vue` | Token 配额可视化 | P2 |
| `knowledge/UrlImporter.vue` | URL 导入对话框 | P1 |
| `workflow/PublishButton.vue` | 工作流发布 | P2 |

**路由增量**

| 路径 | 组件 | 权限 |
| ---- | ---- | ---- |
| `/settings/tools` | `ToolManagement.vue` | `tenant:write` |

---

## 七、数据库 / 迁移增量

| 迁移文件 | 内容 | 优先级 |
| -------- | ---- | ------ |
| `004_refresh_tokens.py` | refresh_tokens 表 | P2 |
| `005_workflow_status.py` | workflows.status / published_at | P2 |
| `006_tenant_tool_configs.py` | tenant_tool_configs 表 | P2 |
| `007_rag_eval_samples.py` | rag_eval_samples 表 | P2 |

**说明**：所有迁移必须通过 Alembic 管理，禁止手工改表。

---

## 八、三期开发排期

| 周次 | 任务 | 产出 | 优先级 |
| ---- | ---- | ---- | ------ |
| W1 | 后端测试补齐 + CI 覆盖率门禁 ≥70% | 后端 PR + CI 更新 | P0 |
| W2 | arq-worker 容器化 + Playwright 框架 + login/rag E2E | 运维 PR + E2E 2/4 | P0 |
| W3 | agent/workflow E2E + Vitest Store 单测 + validate-graph/replay API | 全栈 PR | P0/P1 |
| W4 | URL 导入 + LangSmith 前端 + 主文档 8~11 章补全 + Runbook | 文档 PR + 功能 PR | P0/P1 |
| W5 | Refresh Token + SQL 白名单 + PythonREPL Docker 沙箱 | 安全 PR | P2 |
| W6 | Prometheus/Grafana + i18n/暗色 + 工具扩展 + 三期验收 | 交付验收 | P1/P2 |

---

## 九、三期验收检查表

### 9.1 功能验收

- [ ] RAG 网页 URL 导入并成功检索
- [ ] 工作流保存前 validate-graph 校验生效
- [ ] 工作流 replay API 返回正确 input_params
- [ ] LangSmith trace 链接可跳转（配置 Key 后）
- [ ] calculator 工具可正常调用
- [ ] 工作流 draft / published 状态流转正确
- [ ] Token 配额超限返回 429 且前端有提示
- [ ] 暗色主题 / 英文界面切换正常

### 9.2 工程验收

- [ ] `pytest --cov-fail-under=70` 通过
- [ ] 前端 Vitest ≥15 用例通过
- [ ] Playwright 4 条主路径 E2E 通过
- [ ] CI PR / main 流水线绿灯（含覆盖率门禁）
- [ ] `docker compose up` 含 arq-worker，15 分钟内全服务可用
- [ ] `docs/DEPLOYMENT_RUNBOOK.md` 完整可用
- [ ] `DEVELOPMENT_DOCUMENT.md` 第 8~11 章正文补全

### 9.3 安全验收

- [ ] Refresh Token 刷新 / 登出黑名单生效
- [ ] PythonREPL Docker 模式无法访问网络 / 文件系统
- [ ] SQL 工具拒绝非 SELECT 与非白名单表
- [ ] 租户隔离渗透测试报告完成（≥20 条用例）
- [ ] 审计日志覆盖登录 / CRUD / 工具调用 / 工作流执行

### 9.4 文档验收

- [ ] API 文档与代码接口一致（可通过 OpenAPI `/docs` 交叉验证）
- [ ] 部署 Runbook 可指导新人 30 分钟内完成本地启动
- [ ] 三期验收检查表全部勾选

---

## 十、风险与依赖

| 风险 | 缓解措施 |
| ---- | -------- |
| LLM 调用成本高，E2E 不稳定 | Playwright 使用 recorded mock fixtures；CI 可选跳过真实 LLM |
| Docker 沙箱增加部署复杂度 | 默认 `local` 模式，生产 compose 才启用 `docker` 模式 |
| 覆盖率 70% 短期难达 | W1 优先覆盖 Service 层与 API 集成，UI 以 E2E 补位 |
| Refresh Token 改动影响现有 JWT 流程 | 双模式兼容：旧客户端仍可用 access_token，新客户端启用 refresh |
| Prometheus / Grafana 非必需 | P2 项，W6 时间不足可延后至 3.1 小版本 |
| 主文档补全工作量大 | 以 OpenAPI 自动生成 + 人工润色方式提速 |

**外部依赖**：

| 依赖 | 用途 | 必需性 |
| ---- | ---- | ------ |
| LLM API Key | RAG / Agent / Workflow | 必需（BYOK） |
| Redis | 进度 / 队列 / 监控 / Checkpoint | 必需 |
| PostgreSQL | 主数据库 | 必需 |
| Pinecone API Key | 线上向量库 | 可选 |
| LangSmith API Key | 链路追踪 | 可选 |
| Docker Engine | PythonREPL 沙箱 | 生产推荐 |

---

## 十一、版本记录

| 版本 | 日期 | 说明 |
| ---- | ---- | ---- |
| v3.0-draft | 2026-06-11 | 初稿，基于二期代码审计与二期验收差距分析 |
| v3.0 | — | 三期开发完成并验收通过后发布 |

---

## 附录 A：三期与二期/P2 项对照

| 二期编号 | 描述 | 二期状态 | 三期处理 |
| -------- | ---- | -------- | -------- |
| P0-01~05 | 一期 P0 | ✅ 二期已关闭 | — |
| P1-01~11 | Monaco/预览/会话等 | ✅ 二期已关闭 | — |
| P1-12 | 文档补全 | ⚠️ 极简 | **三期 P0-04/P0-05** |
| P2-01~02 | 租户/审计 | ✅ 二期已关闭 | — |
| P2-03 | Token 配额 | ❌ | **三期 P2-02 / 4.6.3** |
| P2-04 | arq 队列 | ⚠️ 代码有，compose 无 | **三期 P0-03** |
| P2-05~10 | 安全/监控/体验 | ❌ / ⚠️ | **三期 P2 全量** |
| 二期 8.2 测试 | 覆盖率/E2E | ❌ | **三期 P0 核心** |
| 二期 4.2.2 URL | URL 导入 | ❌ | **三期 P1-01** |
| 二期 4.3.3 工具 | calculator 等 | ❌ | **三期 P1-07 / P2-06** |

---

## 附录 B：推荐执行顺序（单人全栈）

```
W1 测试 → W2 部署/Worker/E2E → W3 API补全/E2E → W4 文档+URL+LangSmith → W5 安全 → W6 可观测+体验+验收
```

若资源有限，**最低可交付路径**（MVP+）：

1. P0 全部（测试 + Worker + 文档 + Runbook）
2. P1-01 ~ P1-04（URL + validate + replay + LangSmith）
3. P2-01（Refresh Token）
4. 其余 P2 按需迭代至 3.1 / 3.2 小版本
