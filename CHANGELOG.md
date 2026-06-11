# Changelog

本文件记录企业智能协作工作台的全部版本变更，格式基于 [Keep a Changelog](https://keepachangelog.com/zh-CN/1.0.0/)。

---

## [1.4.0] - 2026-06-11

### Added

- RAG 检索效果评估脚本 `tests/eval/rag_eval.py`（125 组标准问答对）
- AI 能力评估报告 `docs/reports/AI_EVAL_REPORT.md`
- Locust 性能压测脚本 `tests/perf/locustfile.py`（100 并发场景）
- 性能压测报告 `docs/reports/PERF_REPORT.md`
- 用户操作手册 `docs/USER_MANUAL.md`
- 阶段 2/3 验收报告 `docs/reports/PHASE2_ACCEPTANCE_REPORT.md`、`PHASE3_ACCEPTANCE_REPORT.md`

### Changed

- 运维手册 `docs/DEPLOYMENT_RUNBOOK.md` 增补监控体系与故障预案

---

## [1.3.0] - 2026-06-11 — 阶段 2 核心功能完善

### Added

- RAG 对话历史持久化与会话 UI
- 用户批量导入/导出（CSV）
- 密码复杂度策略校验
- RAG 检索过滤 UI（部门 / 文档类型 / 时间范围）
- Agent 多模型前端选择与 `top_p` 参数
- 工作流并行执行引擎
- 工作流终止 API
- SSE 断开自动重连（最多 3 次）
- 代码块语法高亮（流式 Markdown 渲染）

---

## [1.2.0] - 2026-06-11 — 阶段 1 安全与数据隔离

### Added

- 引用溯源 SSE 事件统一（`type: citation`）
- 租户 Token 配额强制执行（`check_tenant_quota`）
- 提示词注入与敏感内容防护（`guardrails.py`）
- 登录失败 5 次锁定 15 分钟（Redis 计数）
- 前后端权限码统一（`kb:*` 命名体系）
- 知识库删除时向量自动清理（`delete_collection`）
- 可选登录与按需鉴权（`AUTH_MODE` / `accessLevel`）

### Security

- Agent / RAG 入口集成 guardrails 检测
- 审计日志记录关键操作

---

## [1.1.0] - 2026-06-11 — 三期企业级交付

### Added

- 后端测试体系与 CI 覆盖率门禁（≥70%）
- arq-worker Docker 容器化
- 前端 Vitest（15 用例）与 Playwright E2E（4 场景）
- 工作流图校验 REST API（`validate-graph`）
- 工作流重跑 API（`replay`）
- RAG 网页 URL 导入
- Refresh Token 与登出黑名单
- Agent calculator 工具
- Prometheus 指标暴露（`PROMETHEUS_ENABLED`）
- Token 配额服务与租户配额字段
- PythonREPL Docker 沙箱模式
- SQL 工具表白名单
- 暗色主题切换
- 部署 Runbook 与主文档第 8~11 章

### Changed

- `DEVELOPMENT_DOCUMENT.md` 补全 API / 测试 / 部署章节

---

## [1.0.0] - 2026-06-11 — 二期功能补齐

### Added

- Redis 持久化文档解析进度
- KB `chunk_size` / `chunk_overlap` 运行时生效
- 工作流自定义 `graph_definition` 运行时执行
- 执行 Agent 真实 Python / SQL 工具调用
- Monaco Editor 系统提示词编辑
- 文档在线预览（PDF / Word / Excel）
- RAG / 纯 LLM 模式切换（`use_rag`）
- Agent 对话历史 UI 与会话管理
- 工作流可视化编辑器（vue-flow）
- 工作流执行历史与重跑
- PPT / PPTX 文档格式支持
- 检索统计与优化建议 API
- Pinecone 向量库切换（BYOK）
- 用户活跃度 DAU / WAU / MAU 监控
- 租户 CRUD 管理端
- 操作审计日志
- arq 异步任务队列
- GitHub Actions CI 流水线
- Husky pre-commit 钩子

### Fixed

- 工作流执行 Agent Mock 返回问题
- 解析进度进程内存储导致重启丢失

---

## [0.9.0] - 2026-06 — 二期 P0 阻塞项

### Added

- 后端 pytest 单元 / 集成测试骨架
- `graph_builder.build_from_definition()` 自定义拓扑
- 工作流图结构校验服务层

### Fixed

- KB 分块配置未生效
- 文档解析进度易丢失

---

## [0.8.0] - 2026-06 — MVP 增强

### Added

- MiniMax 风格布局重构
- 用户级 API 密钥管理（BYOK 多厂商）
- 系统监控大盘（Token / 接口 / 错误日志）
- Docker Compose 一键部署优化

### Fixed

- 登录失败与后端进程不稳定
- 登录后获取用户信息失败
- Python 3.13 下 SQLAlchemy / requirements 兼容性

---

## [0.7.0] - 2026-05 — LangGraph 多智能体工作流

### Added

- 标准五 Agent 拓扑（调度 / 知识库 / 搜索 / 执行 / 审核）
- Redis Checkpoint 状态持久化
- WebSocket 实时节点状态推送
- vue-flow 工作流执行态可视化
- 人工介入节点

---

## [0.6.0] - 2026-05 — 单 Agent 智能体

### Added

- 智能体 CRUD / 复制
- 内置工具：知识库检索、Tavily 搜索、Python 执行、SQL 查询
- 流式对话与工具调用可视化
- 对话历史持久化（`chat_histories`）
- Agent 执行中断

---

## [0.5.0] - 2026-05 — 增强 RAG 系统

### Added

- 知识库 CRUD 与权限控制
- 多格式文档上传与异步解析
- 7 层 RAG 链路：分块、混合检索、重排序、引用溯源
- 向量全量 / 增量更新
- RAG 流式问答（SSE）与引用标注
- Chroma 本地向量库

---

## [0.4.0] - 2026-05 — 用户体系与权限

### Added

- JWT 登录 / 登出 / 用户信息
- RBAC 角色权限（user / role / kb / agent / workflow / monitor）
- 多租户数据隔离（`tenant_id`）
- 用户 / 角色 CRUD
- AES-256-GCM API 密钥加密存储

---

## [0.1.0] - 2026-05 — 项目初始化

### Added

- 项目脚手架：Vue 3 + FastAPI + PostgreSQL + Redis
- Docker Compose 编排
- Nginx 反向代理
- 基础目录结构与开发规范
