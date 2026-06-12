/** 插件权限中文标签（与后端 permissions.py 对齐） */
export const CATEGORY_LABELS: Record<string, string> = {
  'network:outbound': '对外网络访问',
  'network:inbound': '接收外部请求',
  'storage:read': '读取插件私有存储',
  'storage:write': '写入插件私有存储',
  'system:env': '读取环境变量',
  'agent:message': '发送消息给 Agent',
  'user:info': '获取当前用户信息',
  'filesystem:read': '读取沙箱文件',
  'filesystem:write': '写入沙箱文件',
  'process:spawn': '创建子进程',
  'database:query': '数据库查询',
  'mcp:invoke': '调用 MCP 工具',
};
