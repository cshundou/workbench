"""
Skill 与插件权限常量。
"""

from typing import FrozenSet

# PRD §3.4.2 细粒度权限（10+）
SKILL_PERMISSIONS: dict[str, str] = {
    "network:outbound": "对外网络访问",
    "network:inbound": "接收外部请求",
    "storage:read": "读取插件私有存储",
    "storage:write": "写入插件私有存储",
    "system:env": "读取环境变量",
    "agent:message": "发送消息给 Agent",
    "user:info": "获取当前用户信息",
    "filesystem:read": "读取沙箱文件",
    "filesystem:write": "写入沙箱文件",
    "process:spawn": "创建子进程",
    "database:query": "数据库查询",
    "mcp:invoke": "调用 MCP 工具",
}

VALID_SKILL_PERMISSIONS: FrozenSet[str] = frozenset(SKILL_PERMISSIONS.keys())

PLUGIN_CATEGORIES: list[str] = [
    "office",
    "data",
    "dev",
    "industry",
    "life",
]

CATEGORY_LABELS: dict[str, str] = {
    "office": "办公效率",
    "data": "数据连接",
    "dev": "开发工具",
    "industry": "行业应用",
    "life": "生活服务",
}
