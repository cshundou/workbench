"""
工作流统一工具管理器：内置工具、Skill、MCP 统一解析与调用。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from app.services.user_key_context import UserKeyContext
from app.services.workflow.task_mode_resolver import build_member_node_config
from app.services.workflow.workflow_agent_runner import ROLE_TOOLS, WorkflowAgentRunner

logger = logging.getLogger(__name__)

# 节点配置中可声明的额外工具字段
NODE_TOOL_CONFIG_KEYS = ("tools", "skill_tools", "extra_tools")


class WorkflowToolManager:
    """工作流节点统一工具入口，合并角色默认工具与节点配置。"""

    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        user_ctx: UserKeyContext,
        runner: WorkflowAgentRunner,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_ctx = user_ctx
        self.runner = runner

    def resolve_tool_names(
        self,
        role: str,
        node_config: dict[str, Any] | None = None,
    ) -> list[str]:
        """
        解析节点可用工具列表：角色默认 + tools + skill_tools + extra_tools。

        去重并保持顺序，Skill/MCP 以 skill_key 形式传入 Agent。
        """
        node_config = node_config or {}
        merged: list[str] = []
        seen: set[str] = set()

        def _add(names: list[str] | None) -> None:
            if not names:
                return
            for name in names:
                key = str(name).strip()
                if key and key not in seen:
                    seen.add(key)
                    merged.append(key)

        if not node_config.get("use_member_tools_only"):
            _add(ROLE_TOOLS.get(role, []))
        for field in NODE_TOOL_CONFIG_KEYS:
            raw = node_config.get(field)
            if isinstance(raw, list):
                _add([str(x) for x in raw])
        return merged

    def run_role_agent(
        self,
        role: str,
        task: str,
        *,
        node_config: dict[str, Any] | None = None,
        kb_id: Optional[int] = None,
        model_config: Optional[dict[str, Any]] = None,
        max_iterations: int = 5,
        timeout_seconds: Optional[int] = None,
        system_prompt: Optional[str] = None,
        member_config: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """通过统一工具列表执行角色 Agent。"""
        effective_config = dict(node_config or {})
        if member_config:
            effective_config = build_member_node_config(member_config, effective_config)
        tools = self.resolve_tool_names(role, effective_config)
        retry_count = int((node_config or {}).get("tool_retry_count", 2))
        last_error: Optional[str] = None
        # 节点配置可覆盖团队/预设角色提示词
        resolved_prompt = system_prompt
        if not resolved_prompt and effective_config:
            raw = effective_config.get("system_prompt")
            if raw:
                resolved_prompt = str(raw).strip() or None

        for attempt in range(max(1, retry_count + 1)):
            try:
                return self.runner.run_sync(
                    role=role,
                    task=task,
                    tools=tools,
                    kb_id=kb_id,
                    model_config=model_config,
                    max_iterations=max_iterations,
                    system_prompt=resolved_prompt,
                )
            except Exception as exc:
                last_error = str(exc)
                logger.warning(
                    "工具调用失败 role=%s attempt=%s/%s: %s",
                    role,
                    attempt + 1,
                    retry_count + 1,
                    exc,
                )
        return {
            "answer": "",
            "tool_calls": [],
            "duration_ms": 0,
            "error": last_error or "工具调用失败",
        }

    def run_skill(
        self,
        skill_key: str,
        task: str,
        *,
        node_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """执行单个 Skill 工具（以 skill_key 作为 Agent 工具名）。"""
        config = dict(node_config or {})
        config["tools"] = [skill_key]
        return self.run_role_agent(
            role="execution",
            task=task,
            node_config=config,
            max_iterations=int(config.get("max_iterations", 3)),
        )
