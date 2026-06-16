"""
任务模式能力解析：将团队成员 execution_mode / task_tools 映射为可执行工具。
"""

from __future__ import annotations

from typing import Any

from app.services.agent.tools import (
    TOOL_KNOWLEDGE_BASE,
    TOOL_PYTHON_REPL,
    TOOL_SQL_QUERY,
    TOOL_TAVILY_SEARCH,
    TOOL_UI_AUTOMATION,
)

# 任务能力别名 → 内置工具名
TASK_TOOL_ALIAS_MAP: dict[str, str] = {
    "browser": TOOL_UI_AUTOMATION,
    "ui_automation": TOOL_UI_AUTOMATION,
    "terminal": TOOL_PYTHON_REPL,
    "python": TOOL_PYTHON_REPL,
    "python_repl": TOOL_PYTHON_REPL,
    "search": TOOL_TAVILY_SEARCH,
    "tavily_search": TOOL_TAVILY_SEARCH,
    "knowledge": TOOL_KNOWLEDGE_BASE,
    "knowledge_base_search": TOOL_KNOWLEDGE_BASE,
    "sql": TOOL_SQL_QUERY,
    "sql_query": TOOL_SQL_QUERY,
}

_TASK_CAPABILITY_TOOLS = frozenset(
    {"search", "python", "sql", "knowledge", "knowledge_base_search", "tavily_search", "ui_automation"}
)


def infer_execution_mode(member: dict[str, Any]) -> str:
    """推断成员执行模式：llm 或 task。"""
    mode = str(member.get("execution_mode") or "").strip().lower()
    if mode in ("llm", "task"):
        return mode
    tools = {str(t).strip().lower() for t in (member.get("tools") or [])}
    if tools & _TASK_CAPABILITY_TOOLS:
        return "task"
    return "llm"


def resolve_task_tool_names(member: dict[str, Any]) -> list[str]:
    """
    将 task_tools / tools 解析为 Agent 可调用工具名列表。

    优先使用 task_tools（browser/terminal），再补充角色 tools 字段映射。
    """
    resolved: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        key = str(raw).strip().lower()
        if not key:
            return
        tool_name = TASK_TOOL_ALIAS_MAP.get(key, key)
        if tool_name not in seen:
            seen.add(tool_name)
            resolved.append(tool_name)

    for item in member.get("task_tools") or []:
        _add(str(item))
    for item in member.get("tools") or []:
        _add(str(item))
    return resolved


def build_member_node_config(
    member: dict[str, Any],
    base_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    根据成员任务模式生成节点 config（含 tools / execution_mode 快照）。
    """
    config = dict(base_config or {})
    mode = infer_execution_mode(member)
    config["execution_mode"] = mode
    if mode == "task":
        tools = resolve_task_tool_names(member)
        if tools:
            config["tools"] = tools
            config["use_member_tools_only"] = True
    return config
