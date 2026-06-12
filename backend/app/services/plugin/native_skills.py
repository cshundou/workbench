"""
平台原生 Skill 目录（5 个内置工具 + MCP 桥接）。
"""

from typing import Any

from app.services.agent.tools import (
    AVAILABLE_TOOL_DEFINITIONS,
    TOOL_CALCULATOR,
    TOOL_KNOWLEDGE_BASE,
    TOOL_PYTHON_REPL,
    TOOL_SQL_QUERY,
    TOOL_TAVILY_SEARCH,
)

# PRD 要求的 5 个标准内置 Skill
NATIVE_SKILL_KEYS: list[str] = [
    TOOL_KNOWLEDGE_BASE,
    TOOL_TAVILY_SEARCH,
    TOOL_PYTHON_REPL,
    TOOL_SQL_QUERY,
    TOOL_CALCULATOR,
]

TOOL_PERMISSION_MAP: dict[str, list[str]] = {
    TOOL_KNOWLEDGE_BASE: ["database:query"],
    TOOL_TAVILY_SEARCH: ["network:outbound"],
    TOOL_PYTHON_REPL: ["process:spawn", "filesystem:read"],
    TOOL_SQL_QUERY: ["database:query"],
    TOOL_CALCULATOR: [],
}


def build_native_skill_defs() -> list[dict[str, Any]]:
    """从内置工具元数据生成原生 Skill 定义。"""
    by_name = {item["name"]: item for item in AVAILABLE_TOOL_DEFINITIONS}
    defs: list[dict[str, Any]] = []
    for key in NATIVE_SKILL_KEYS:
        meta = by_name.get(key, {})
        defs.append(
            {
                "skill_key": key,
                "name": meta.get("label", key),
                "description": meta.get("description", ""),
                "source_type": "native",
                "permissions": TOOL_PERMISSION_MAP.get(key, []),
                "is_native": True,
                "version": "1.0.0",
                "icon": "🔧",
                "tags": ["builtin", "native"],
            }
        )
    return defs
