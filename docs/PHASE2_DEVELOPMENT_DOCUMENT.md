# 企业智能协作工作台 — 二期开发文档

**文档版本**：v2.0-draft  
**编制日期**：2026-06-11  
**前置基线**：一期 MVP（`docs/DEVELOPMENT_DOCUMENT.md` v1.0）  
**适用对象**：前端开发者、后端 / AI 开发者、全栈开发者、运维工程师

---

## 一、一期交付现状摘要

### 1.1 已实现功能清单

| 模块                 | 功能点                                               | 实现状态              | 主要路径                               |
| -------------------- | ---------------------------------------------------- | --------------------- | -------------------------------------- |
| **账户 & 权限**      | JWT 登录 / 登出 / 获取用户信息                       | ✅                     | `backend/app/api/v1/auth.py`           |
|                      | RBAC 角色权限（user/role/kb/agent/workflow/monitor） | ✅                     | `backend/app/core/permissions.py`      |
|                      | 多租户数据隔离（tenant_id）                          | ✅                     | 各 Service 层                          |
|                      | 用户 / 角色 CRUD                                     | ✅                     | `users.py`, `roles.py` + 前端 Settings |
|                      | 用户自管 API Key（多厂商 BYOK）                      | ✅ 超出一期文档        | `user_api_keys.py`                     |
| **增强 RAG**         | 知识库 CRUD + 权限                                   | ✅                     | `knowledge_bases.py`                   |
|                      | 多格式文档上传（PDF/TXT/MD/DOCX/XLSX/HTML）          | ✅                     | `document_loader.py`                   |
|                      | 7 层 RAG 链路（分块/混合检索/重排/引用）             | ✅ 部分                | `rag/` 目录                            |
|                      | 文档解析进度                                         | ⚠️ 进程内存，重启丢失  | `rag_service.py`                       |
|                      | 向量全量 / 增量更新                                  | ✅                     | `rag_service.py`                       |
|                      | RAG 流式问答 + 引用标注                              | ✅                     | `knowledge/Chat.vue`                   |
|                      | 检索效果统计 / 优化建议                              | ❌                     | —                                      |
|                      | PPT / 网页链接接入                                   | ❌                     | —                                      |
| **单 Agent**         | 智能体 CRUD / 复制                                   | ✅                     | `agents.py`                            |
|                      | 系统提示词编辑                                       | ⚠️ textarea，非 Monaco | `AgentConfigForm.vue`                  |
|                      | 4 种内置工具                                         | ✅                     | `agent/tools/`                         |
|                      | 流式对话 + 工具调用可视化 + 中断                     | ✅                     | `agents/Chat.vue`                      |
|                      | 对话历史持久化                                       | ✅ 后端                | `ChatHistory` 模型                     |
|                      | 对话历史 UI                                          | ❌                     | API 已有，前端未用                     |
| **LangGraph 工作流** | 标准五 Agent 拓扑执行                                | ✅                     | `graph_builder.py`                     |
|                      | 人工介入节点                                         | ✅                     | `workflow_service.py`                  |
|                      | Redis Checkpoint                                     | ✅                     | `redis_saver.py`                       |
|                      | WebSocket 实时节点状态                               | ✅                     | `workflow_ws.py`                       |
|                      | vue-flow 执行态可视化                                | ✅                     | `WorkflowCanvas.vue`                   |
|                      | 工作流可视化编辑器                                   | ❌                     | 仅标准模板                             |
|                      | 自定义 graph_definition 运行时执行                   | ❌                     | 存库但未驱动执行                       |
|                      | 执行历史页面                                         | ❌                     | API 已有                               |
|                      | 执行 Agent 真实工具调用                              | ❌                     | Mock 返回                              |
| **流式交互**         | SSE（RAG）+ Fetch Stream（Agent）                    | ✅                     | `sse.ts`, `agent.ts`                   |
|                      | Markdown / 代码块渲染                                | ✅                     | `StreamingText.vue`                    |
|                      | WebSocket（工作流）                                  | ✅                     | `graph.ts`                             |
| **系统监控**         | Token 消耗统计                                       | ✅                     | `monitor.py`                           |
|                      | API 调用量 / 响应时间                                | ✅                     | Redis 计数                             |
|                      | 错误日志查询                                         | ✅                     | Redis 列表                             |
|                      | 健康检查                                             | ✅                     | DB + Redis                             |
|                      | 用户活跃度统计                                       | ❌                     | —                                      |
| **部署**             | Docker Compose 编排                                  | ✅                     | `docker-compose.yml`                   |
|                      | Nginx 反向代理                                       | ✅                     | `nginx/nginx.conf`                     |
| **测试 & CI**        | 单元 / 集成 / E2E 测试                               | ❌                     | 无 test 目录                           |
|                      | CI 流水线                                            | ❌                     | 无 `.github/workflows`                 |

### 1.2 一期与开发文档符合度评估

| 维度                               | 符合度  | 说明                                                         |
| ---------------------------------- | ------- | ------------------------------------------------------------ |
| 技术栈主体                         | **85%** | Vue3/Pinia/FastAPI/LangChain/LangGraph/PostgreSQL/Redis/Chroma 已落地 |
| 数据库表结构                       | **95%** | 与文档 4.2 基本一致，额外增加 `user_api_keys`                |
| API 接口（8.2~8.4 已写部分）       | **90%** | 52 个 REST + 1 WebSocket，覆盖认证/知识库/智能体/工作流/监控 |
| 三大核心技术（RAG/Agent/Workflow） | **75%** | 核心链路通，若干高级特性未落地                               |
| 前端交互规范（第 7 章）            | **65%** | 缺 Monaco、文档预览、通用组件库、部分 Store 导出不全         |
| 测试指南（第 10 章）               | **0%**  | 文档目录有，正文未写；代码无测试                             |
| 部署指南（第 11 章）               | **60%** | 有 docker-compose，缺完整 Runbook                            |
| 开发文档自身完整性                 | **70%** | 第 8.4 节后截断，第 9~15 章仅有目录无正文                    |

**结论：一期达到「可演示 MVP / 技术验证」标准，尚未达到开发文档宣称的「企业级可直接交付」标准。**

---

## 二、一期未达标项（二期必须补齐）

### 2.1 P0 — 阻塞交付

| 编号  | 缺口                                       | 文档依据  | 影响                             |
| ----- | ------------------------------------------ | --------- | -------------------------------- |
| P0-01 | 零自动化测试                               | 第 10 章  | 无法保证回归、不符合企业交付门禁 |
| P0-02 | 工作流 `graph_definition` 未驱动运行时     | 6.4       | 前后端工作流能力不一致           |
| P0-03 | 执行 Agent 为 Mock                         | 5.3.1     | 工作流「任务自动化」承诺未兑现   |
| P0-04 | 文档解析进度进程内存储                     | 6.2       | 重启丢状态，无法生产使用         |
| P0-05 | KB `chunk_size`/`chunk_overlap` 配置未生效 | 4.2 / 5.1 | 数据模型与运行时不一致           |

### 2.2 P1 — 文档明确要求

| 编号  | 缺口                                   | 文档依据    |
| ----- | -------------------------------------- | ----------- |
| P1-01 | Monaco Editor 提示词编辑               | 2.1 / 6.3   |
| P1-02 | 文档在线预览（PDF/Word/Excel）         | 2.1 / 6.2   |
| P1-03 | RAG 模式切换（纯 LLM / 知识库增强）    | 5.1         |
| P1-04 | Agent 对话历史 UI + 会话管理           | 5.2.2 / 6.3 |
| P1-05 | 工作流可视化编辑器                     | 6.4         |
| P1-06 | 工作流执行历史与重跑                   | 6.4 / 6.5   |
| P1-07 | PPT 格式支持                           | 5.1.1       |
| P1-08 | Pinecone 线上向量库切换                | 2.2 / 4.1   |
| P1-09 | LangSmith 链路追踪                     | 2.2 / 5.3.3 |
| P1-10 | 检索效果统计与优化建议                 | 6.2         |
| P1-11 | 用户活跃度统计                         | 6.6         |
| P1-12 | 补全开发文档第 8.4~8.8、第 9~11 章正文 | 目录        |

### 2.3 P2 — 企业增强（文档隐含 / 最佳实践）

| 编号  | 缺口                       | 说明                       |
| ----- | -------------------------- | -------------------------- |
| P2-01 | 租户管理 API + 管理端      | 模型已有，无 CRUD          |
| P2-02 | 操作审计日志               | 3.4 安全架构               |
| P2-03 | Token 配额 / 限流可视化    | 3.4                        |
| P2-04 | 异步任务队列（Celery/RQ）  | 替代 `asyncio.create_task` |
| P2-05 | Agent PythonREPL 容器沙箱  | 安全加固                   |
| P2-06 | SQL 工具只读副本 + 白名单  | 生产安全                   |
| P2-07 | Refresh Token / 登出黑名单 | 安全增强                   |
| P2-08 | Prometheus + Grafana 指标  | 2.3 可选栈                 |
| P2-09 | 前端 i18n / 暗色主题       | 企业体验                   |
| P2-10 | Husky + ESLint CI 门禁     | 2.1 工程化                 |

---

## 三、二期总体目标

**目标定位**：在一期 MVP 基础上，补齐开发文档全部功能缺口，达到可对外交付的企业级标准。

**交付标准（二期验收）**：

1. 开发文档第 6 章全部功能点实现率 ≥ 95%
2. 后端核心模块单元测试覆盖率 ≥ 70%
3. 关键用户路径 E2E 测试通过（登录 → RAG 问答 → Agent 对话 → 工作流执行）
4. `docker compose up` 一键启动，配套部署 Runbook
5. 工作流支持可视化编辑 + 自定义拓扑执行
6. 无 P0 级已知缺陷

---

## 四、二期功能需求详述

### 4.1 工程化与质量保障（第 9~10 周计划落地）

#### 4.1.1 测试体系

**后端（pytest）**

```
backend/tests/
├── conftest.py              # 异步 DB fixture、测试客户端
├── unit/
│   ├── test_auth.py
│   ├── test_rag_chunker.py
│   ├── test_rag_retriever.py
│   ├── test_agent_tools.py
│   └── test_permissions.py
├── integration/
│   ├── test_knowledge_api.py
│   ├── test_agent_api.py
│   └── test_workflow_api.py
└── e2e/
    └── test_full_pipeline.py
```

**前端（Vitest + Playwright）**

```
frontend/
├── src/**/*.spec.ts         # 组件 / Store 单测
└── e2e/
    ├── login.spec.ts
    ├── rag-chat.spec.ts
    └── workflow-execute.spec.ts
```

**CI（GitHub Actions）**

- PR 触发：lint → unit test → integration test
- main 分支：额外 E2E（可选 mock LLM）

#### 4.1.2 补全一期开发文档

- 完成 `DEVELOPMENT_DOCUMENT.md` 第 8.4~8.8 节（智能体 / 工作流 / 流式 / 监控 API）
- 编写第 9 章分阶段计划正文（标注一期已完成项）
- 编写第 10 章测试指南、第 11 章部署指南

---

### 4.2 RAG 增强（模块 6.2）

#### 4.2.1 配置一致性修复

- `IntelligentChunker` 读取 KB 表的 `chunk_size`、`chunk_overlap`、`embedding_model`
- 解析进度写入 Redis（key: `parse_progress:{doc_id}`），支持多实例

#### 4.2.2 格式扩展

- 新增 PPT/PPTX 解析（`unstructured.partition.pptx`）
- 网页链接导入：URL → 抓取 → 入库（可选开关）

#### 4.2.3 Pinecone 向量库

- 环境变量 `VECTOR_STORE=chroma|pinecone`
- `rag_service.py` 抽象 `VectorStoreBackend` 接口
- 用户配置 Pinecone API Key 后可选线上索引

#### 4.2.4 检索分析与优化

**新增 API**

| 方法 | 路径                                          | 说明                          |
| ---- | --------------------------------------------- | ----------------------------- |
| GET  | `/knowledge-bases/{kb_id}/search-stats`       | 检索次数、命中率、平均延迟    |
| GET  | `/knowledge-bases/{kb_id}/optimization-hints` | 分块过大/过小、低命中文档建议 |

**前端**：知识库详情页新增「检索分析」Tab（ECharts）

#### 4.2.5 文档预览

- 前端集成 PDF.js、mammoth（Word）、XLSX
- 组件：`DocumentPreview.vue`
- 知识库详情支持点击文档在线预览

#### 4.2.6 RAG 模式切换

- 知识库 Chat 页增加 Switch：`知识库增强` / `纯大模型`
- 请求参数 `use_rag: boolean`

---

### 4.3 Agent 增强（模块 6.3）

#### 4.3.1 Monaco Editor

- 依赖：`monaco-editor@0.47.x`
- 组件：`PromptEditor.vue`（语法高亮、行号、全屏）
- 替换 `AgentConfigForm.vue` 中 textarea

#### 4.3.2 对话历史与会话

**前端**

- `AgentChat.vue` 左侧会话列表（按 `session_id` 分组）
- 加载历史消息含 `tool_start` / `tool_end` 元数据
- 新建会话 / 删除会话

**后端**

- `GET /agents/{id}/history` 支持 `session_id` 过滤（已有则扩展）
- `DELETE /agents/{id}/history/{session_id}`

#### 4.3.3 工具市场扩展

- 工具注册表支持动态加载配置
- 二期新增：`calculator`（计算器）、`web_scraper`（可选）
- 管理端工具启用开关（租户级）

---

### 4.4 LangGraph 工作流增强（模块 6.4）

#### 4.4.1 可视化工作流编辑器

**前端路由**：`/workflows/:id/edit`

**能力**

- vue-flow 可编辑模式：拖拽添加节点、连线、删除
- 节点类型：scheduler / knowledge / search / execution / human / reviewer
- 节点配置面板：提示词覆盖、是否启用人工审核
- 保存至 `graph_definition` JSON

**节点 Schema**

```json
{
  "nodes": [
    {
      "id": "knowledge_agent",
      "type": "knowledge",
      "label": "知识库 Agent",
      "position": { "x": 100, "y": 160 },
      "config": {
        "kb_ids": [1, 2],
        "top_k": 5
      }
    }
  ],
  "edges": [
    { "id": "e1", "source": "scheduler", "target": "knowledge_agent" }
  ]
}
```

#### 4.4.2 运行时执行自定义图

- `workflow_service.execute()` 优先读取 `workflow.graph_definition`
- `graph_builder.py` 新增 `build_from_definition(definition: dict)`
- 校验：必须有且仅有一个 scheduler 入口、无环、节点类型合法
- 无自定义定义时回退 `STANDARD_GRAPH_DEFINITION`

#### 4.4.3 执行 Agent 真实化

- `execution_agent_node` 调用 `PythonReplTool` / `SqlQueryTool`
- 根据子任务类型自动选择工具
- 超时 30s，失败写入 `state["error"]`

#### 4.4.4 执行历史

**前端路由**：`/workflows/:id/history`

- 列表：执行 ID、状态、耗时、输入摘要
- 详情：复用 Execute 页只读模式（canvas + logs）
- 操作：「重新执行」带入历史 input_params

---

### 4.5 系统监控增强（模块 6.6）

#### 4.5.1 用户活跃度

**API**：`GET /monitor/user-activity`

| 字段            | 说明              |
| --------------- | ----------------- |
| dau / wau / mau | 日 / 周 / 月活    |
| top_users       | 活跃用户数 Top 10 |
| module_usage    | 各模块访问占比    |

**数据来源**：Redis HyperLogLog + 模块访问计数

#### 4.5.2 LangSmith 集成

- 环境变量：`LANGCHAIN_TRACING_V2=true`、`LANGCHAIN_API_KEY`
- RAG / Agent / Workflow 链路自动上报
- 监控页增加「追踪链接」跳转（有 trace_id 时）

---

### 4.6 安全与运维增强

#### 4.6.1 审计日志

**新表 `audit_logs`**

```sql
CREATE TABLE audit_logs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id INTEGER NOT NULL,
    user_id INTEGER,
    action VARCHAR(64) NOT NULL,
    resource_type VARCHAR(32),
    resource_id INTEGER,
    detail JSONB,
    ip_address VARCHAR(45),
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

- 记录：登录、CRUD、工具调用、工作流执行
- API：`GET /audit-logs`（`audit:read` 权限）
- 前端：设置 → 审计日志（管理员）

#### 4.6.2 异步任务队列

- 引入 `arq` 或 `celery`（与文档技术栈对齐选 arq + Redis，轻量）
- 文档解析、向量重建、工作流执行入队
- 任务状态 API：`GET /tasks/{task_id}`

#### 4.6.3 租户管理

- API：`/tenants` CRUD（超管专用）
- 前端：设置 → 租户管理
- 配额字段：`max_users`、`max_kb_count`、`monthly_token_limit`

---

## 五、二期 API 增量清单

| 模块     | 方法   | 路径                                          | 说明         |
| -------- | ------ | --------------------------------------------- | ------------ |
| RAG      | GET    | `/knowledge-bases/{kb_id}/search-stats`       | 检索统计     |
| RAG      | GET    | `/knowledge-bases/{kb_id}/optimization-hints` | 优化建议     |
| RAG      | POST   | `/knowledge-bases/{kb_id}/import-url`         | URL 导入     |
| Agent    | DELETE | `/agents/{id}/history/{session_id}`           | 删除会话     |
| Workflow | POST   | `/workflows/{id}/validate-graph`              | 校验图定义   |
| Workflow | GET    | `/workflows/{id}/executions/{eid}/replay`     | 获取重跑参数 |
| Monitor  | GET    | `/monitor/user-activity`                      | 用户活跃度   |
| Audit    | GET    | `/audit-logs`                                 | 审计日志     |
| Tenant   | CRUD   | `/tenants`                                    | 租户管理     |
| Task     | GET    | `/tasks/{task_id}`                            | 异步任务状态 |

---

## 六、二期前端路由增量

| 路径                     | 组件                   | 权限             |
| ------------------------ | ---------------------- | ---------------- |
| `/workflows/:id/edit`    | `WorkflowEdit.vue`     | `workflow:write` |
| `/workflows/:id/history` | `WorkflowHistory.vue`  | `workflow:read`  |
| `/settings/tenants`      | `TenantManagement.vue` | `tenant:read`    |
| `/settings/audit-logs`   | `AuditLogs.vue`        | `audit:read`     |

---

## 七、二期开发排期

| 周次 | 任务                                                   | 产出           |
| ---- | ------------------------------------------------------ | -------------- |
| W1   | P0 修复：chunk 配置、解析进度 Redis、执行 Agent 真实化 | 后端 PR + 单测 |
| W2   | 工作流自定义图运行时 + 图校验 API                      | 后端集成测试   |
| W3   | 工作流可视化编辑器 + 执行历史页                        | 前端 PR        |
| W4   | Monaco、文档预览、Agent 会话、RAG 模式切换             | 前端 PR        |
| W5   | Pinecone、检索分析、LangSmith、用户活跃度              | 全栈           |
| W6   | 测试补齐、CI、审计日志、租户管理、文档补全             | 交付验收       |

---

## 八、二期验收检查表

### 8.1 功能验收

- [ ] 上传 PPT 并成功检索
- [ ] KB 分块参数修改后重新入库生效
- [ ] 文档解析进度在服务重启后仍可查询
- [ ] Agent 提示词 Monaco 编辑保存正常
- [ ] Agent 可查看 / 切换历史会话
- [ ] 知识库 Chat 可切换纯 LLM / RAG 模式
- [ ] 文档 PDF/Word/Excel 在线预览
- [ ] 工作流可视化编辑并保存
- [ ] 自定义工作流拓扑可执行完成
- [ ] 执行 Agent 真实调用 Python/SQL 工具
- [ ] 工作流执行历史查看与重跑
- [ ] 检索分析图表展示
- [ ] 监控面板展示 DAU/MAU
- [ ] LangSmith 可查看 trace（配置后）
- [ ] Pinecone 模式切换可用（配置后）

### 8.2 工程验收

- [ ] `pytest` 覆盖率 ≥ 70%
- [ ] 前端 Vitest 核心 Store / 组件测试通过
- [ ] Playwright E2E 4 条主路径通过
- [ ] GitHub Actions CI 绿灯
- [ ] `docker compose up` 全新环境 15 分钟内可用
- [ ] 部署 Runbook 文档完整

### 8.3 安全验收

- [ ] 审计日志记录关键操作
- [ ] 租户间数据隔离渗透测试通过
- [ ] PythonREPL 沙箱无法执行危险 import
- [ ] SQL 工具仅允许 SELECT

---

## 九、风险与依赖

| 风险                            | 缓解措施                          |
| ------------------------------- | --------------------------------- |
| LangSmith / Pinecone 需外部账号 | 提供 Mock 模式，无 Key 时优雅降级 |
| Monaco 打包体积增大             | 动态 import + vite 分包           |
| 自定义工作流图校验复杂          | 一期仅支持 DAG，禁止环            |
| LLM 调用成本高                  | E2E 使用 recorded mock fixtures   |

---

## 十、版本记录

| 版本       | 日期       | 说明                                           |
| ---------- | ---------- | ---------------------------------------------- |
| v2.0-draft | 2026-06-11 | 初稿，基于一期代码审计与 v1.0 开发文档差距分析 |