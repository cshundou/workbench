"""
工作流子 Agent ReAct 执行器。

封装系统提示词 + 工具集 + 权限检查，供 LangGraph 节点同步调用。
"""

import json
import logging
import time
from typing import Any, Optional

from sqlalchemy import select

from app.core.deps import get_user_permissions
from app.models.user import User
from app.services.agent.agent_service import agent_service
from app.services.agent.tools import (
    TOOL_CALCULATOR,
    TOOL_KNOWLEDGE_BASE,
    TOOL_PYTHON_REPL,
    TOOL_SQL_QUERY,
    TOOL_TAVILY_SEARCH,
)
from app.services.user_key_context import UserKeyContext
from app.utils.async_runner import ephemeral_db_session, run_coro_in_fresh_loop

logger = logging.getLogger(__name__)

# 工作流内置角色默认工具集
ROLE_TOOLS: dict[str, list[str]] = {
    "knowledge": [TOOL_KNOWLEDGE_BASE],
    "search": [TOOL_TAVILY_SEARCH],
    "execution": [TOOL_PYTHON_REPL, TOOL_SQL_QUERY, TOOL_CALCULATOR],
}

ROLE_SYSTEM_PROMPTS: dict[str, str] = {
    "knowledge": (
        "你是企业知识库专家。使用知识库检索工具查询内部资料，"
        "基于检索结果给出准确、简洁的回答。若工具无权限或检索失败，明确说明原因。"
    ),
    "search": (
        "你是联网搜索专家。使用搜索工具获取外部最新信息，"
        "整合多条结果后给出客观摘要。"
    ),
    "execution": (
        "你是数据分析与代码执行专家。根据任务选择合适的工具"
        "（Python 代码、SQL 查询或计算器）完成计算与数据处理。"
    ),
}


class WorkflowAgentRunner:
    """在工作流节点中运行带工具的 Agent。"""

    def __init__(
        self,
        tenant_id: int,
        user_id: int,
        user_ctx: UserKeyContext,
    ) -> None:
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.user_ctx = user_ctx

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """在同步节点中执行协程（独立 loop，避免跨 loop 复用连接池）。"""
        return run_coro_in_fresh_loop(coro)

    async def _load_user(self, db: Any) -> User:
        stmt = select(User).where(User.id == self.user_id)
        user = (await db.execute(stmt)).scalar_one()
        return user

    async def run_async(
        self,
        role: str,
        task: str,
        *,
        system_prompt: Optional[str] = None,
        tools: Optional[list[str]] = None,
        kb_id: Optional[int] = None,
        model_config: Optional[dict[str, Any]] = None,
        max_iterations: int = 5,
    ) -> dict[str, Any]:
        """
        异步运行子 Agent。

        Returns:
            {"answer": str, "tool_calls": list[dict], "duration_ms": int}
        """
        started = time.monotonic()
        tool_names = tools or ROLE_TOOLS.get(role, [])
        prompt = system_prompt or ROLE_SYSTEM_PROMPTS.get(role, "你是专业助手，请完成任务。")

        agent_config: dict[str, Any] = {
            "system_prompt": prompt,
            "tools": tool_names,
            "temperature": 0.3,
            "max_tokens": 2048,
            "top_p": 1.0,
            "model_name": "gpt-3.5-turbo",
        }
        if model_config:
            agent_config.update(model_config)

        # 知识库角色在查询中附带 kb_id 提示
        user_query = task
        if role == "knowledge" and kb_id is not None:
            user_query = f"{task}\n\n请优先在知识库 ID={kb_id} 中检索。"

        async with ephemeral_db_session() as db:
            user = await self._load_user(db)
            result = await agent_service.run_agent(
                agent_config=agent_config,
                user_query=user_query,
                db=db,
                tenant_id=self.tenant_id,
                user=user,
                user_ctx=self.user_ctx,
            )
            await db.commit()

        tool_calls: list[dict[str, Any]] = []
        for step in result.get("intermediate_steps", []):
            tool_calls.append(
                {
                    "tool_name": step.get("tool_name"),
                    "tool_input": step.get("tool_input"),
                    "tool_output": step.get("tool_output"),
                }
            )

        duration_ms = int((time.monotonic() - started) * 1000)
        return {
            "answer": result.get("answer", ""),
            "tool_calls": tool_calls,
            "duration_ms": duration_ms,
        }

    def run_sync(
        self,
        role: str,
        task: str,
        **kwargs: Any,
    ) -> dict[str, Any]:
        """同步封装，供 LangGraph 节点调用。"""
        return self._run_async(self.run_async(role, task, **kwargs))

    async def run_custom_agent_async(
        self,
        agent_id: int,
        task: str,
    ) -> dict[str, Any]:
        """加载用户自定义 Agent 配置并执行。"""
        from app.models.agent import Agent

        started = time.monotonic()
        async with ephemeral_db_session() as db:
            stmt = select(Agent).where(
                Agent.id == agent_id,
                Agent.tenant_id == self.tenant_id,
            )
            agent_row = (await db.execute(stmt)).scalar_one_or_none()
            if agent_row is None:
                return {
                    "answer": "",
                    "tool_calls": [],
                    "duration_ms": 0,
                    "error": "绑定的智能体不存在",
                }

            user = await self._load_user(db)
            permissions = get_user_permissions(user)
            if agent_row.owner_id != user.id and not agent_row.is_public:
                return {
                    "answer": "",
                    "tool_calls": [],
                    "duration_ms": 0,
                    "error": "无权使用该智能体",
                }

            agent_config = {
                "system_prompt": agent_row.system_prompt,
                "tools": list(agent_row.tools or []),
                "temperature": agent_row.temperature,
                "top_p": agent_row.top_p,
                "max_tokens": agent_row.max_tokens,
                "model_name": agent_row.model_name,
                "model_priorities": list(agent_row.model_priorities or []),
            }
            result = await agent_service.run_agent(
                agent_config=agent_config,
                user_query=task,
                db=db,
                tenant_id=self.tenant_id,
                user=user,
                user_ctx=self.user_ctx,
            )
            await db.commit()

        tool_calls = [
            {
                "tool_name": s.get("tool_name"),
                "tool_input": s.get("tool_input"),
                "tool_output": s.get("tool_output"),
            }
            for s in result.get("intermediate_steps", [])
        ]
        return {
            "answer": result.get("answer", ""),
            "tool_calls": tool_calls,
            "duration_ms": int((time.monotonic() - started) * 1000),
        }

    def run_custom_agent_sync(self, agent_id: int, task: str) -> dict[str, Any]:
        return self._run_async(self.run_custom_agent_async(agent_id, task))
