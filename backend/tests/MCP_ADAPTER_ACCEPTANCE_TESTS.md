# MCP 协议适配器 — 验收测试用例

| 编号 | 用例 | 步骤 | 预期 |
|------|------|------|------|
| AT-MCP-01 | HTTP 连接测试 | POST `/mcp/servers/{id}/test` | success=true，返回 server_info |
| AT-MCP-02 | 工具同步 | POST `/mcp/servers/{id}/sync` | synced_count >= 0 |
| AT-MCP-03 | 实时工具列表 | GET `/mcp/servers/{id}/tools/live` | 返回标准 inputSchema |
| AT-MCP-04 | 工具调用 | POST `/mcp/servers/{id}/call` | 返回 content 数组 |
| AT-MCP-05 | 资源列表 | GET `/mcp/servers/{id}/resources` | 返回 uri/name 列表 |
| AT-MCP-06 | stdio 配置 | 创建 transport=stdio + config.command | 创建成功 |
| AT-MCP-07 | 内置预设 | POST `/mcp/builtin/enable` | created_count >= 0 |
| AT-MCP-08 | 单元测试 | pytest test_mcp_adapter.py | 13 passed |
