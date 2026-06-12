# S13 迭代开发文档

**对应需求**: `ITERATION_S13_REQUIREMENTS.md`

---

## 一、任务拆分与文件映射

### 模块 A：群聊协同补全

| 任务 | 文件 | 说明 |
|------|------|------|
| A1 路由 | `frontend/src/router/index.ts` | 增加 `WorkflowGroupChat` |
| A2 取消 | `group_chat_service.py`, `group_chat.py` | `cancel_session` + 流式执行中检测 |
| A3 补充注入 | `group_chat_engine.py`, `group_chat_service.py` | `supplement_loader` 回调 |
| A4 人工审核 | `group_chat_service.py`, `group_chat.py`, `GroupChatView.vue`, `groupChat.ts` | resolve API + UI |
| A5 WS 重连 | `groupChat.ts`, `groupChat.ts` API | 重连 + `getGroupChatMessages` 同步 |

### 模块 B：插件市场完善

| 任务 | 文件 | 说明 |
|------|------|------|
| B1 执行器 | `plugin_handlers.py`, `skill_engine.py` | 官方插件 Skill handler 注册表 |
| B2 门控 | `skill_service.py`, `plugin_service.py`, `agent_service.py` | 安装状态过滤 |
| B3 更新 API | `plugin_service.py`, `plugins.py` | `update_plugin` |
| B4 Agent 工具 | `skill_service.py`, `agents.py` | `list_tools_for_agent` |
| B5 前端安装确认 | `InstallConfirmDialog.vue`, `Marketplace.vue`, `Detail.vue` | 权限弹窗 |
| B6 前端配置/更新 | `Installed.vue`, `PluginConfigDialog.vue` | 配置与更新 |
| B7 市场状态 | `Marketplace.vue`, `plugin_service.py` | 批量查询安装状态 |
| B8 Skill 列表 | `skill_service.py`, `SkillsConfig.vue` | 租户启用态 |
| B9 工具修复 | `ui_automation.py` | `parameters` schema |

### 模块 C：测试

| 任务 | 文件 |
|------|------|
| C1 | `test_group_chat_service.py` |
| C2 | `test_plugin_install_gating.py` |

---

## 二、接口设计

### 群聊

```
POST /api/v1/group-chat/sessions/{id}/cancel
POST /api/v1/group-chat/sessions/{id}/resolve
  body: { "action": "approve" | "reject", "comment": "..." }
```

### 插件

```
POST /api/v1/plugins/{plugin_id}/update
GET  /api/v1/plugins/marketplace  # 响应 items[].installation_status
```

### Agent 工具

```
GET /api/v1/agents/tools
  # 增加 source: native|mcp|plugin, skill_key
```

---

## 三、实现顺序

1. B9 UiAutomationTool（阻塞对话）
2. A1 群聊路由
3. A2–A5 群聊后端 + 前端
4. B1–B4 插件后端
5. B5–B8 插件前端
6. C1–C2 测试

---

## 四、开发状态

| ID | 状态 |
|----|------|
| MA-01 ~ MA-05 | ✅ 已完成 |
| PM-01 ~ PM-09 | ✅ 已完成 |
