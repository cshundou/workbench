"""
Agent 执行引擎：LangChain OpenAI Tools Agent、工具注册与流式对话。
"""

import asyncio
import json
import uuid
from typing import Any, AsyncIterator, Dict, List, Optional

from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import StructuredTool
from langchain_openai import ChatOpenAI
from langchain_core.pydantic_v1 import BaseModel, Field, create_model
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.core.permissions import check_tool_permission
from app.models.chat_history import ChatHistory
from app.models.user import User
from app.services.agent.tools import (
    AVAILABLE_TOOL_DEFINITIONS,
    TOOL_CALCULATOR,
    TOOL_KNOWLEDGE_BASE,
    TOOL_PYTHON_REPL,
    TOOL_SQL_QUERY,
    TOOL_TAVILY_SEARCH,
)
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.agent.tools.knowledge_base import KnowledgeBaseTool
from app.services.agent.tools.calculator import CalculatorTool
from app.services.agent.tools.python_repl import PythonReplTool
from app.services.agent.tools.sql_query import SqlQueryTool
from app.services.agent.tools.tavily_search import TavilySearchTool
from app.core.deps import get_user_permissions
from app.core.guardrails import guardrails_service
from app.services.token_quota_service import token_quota_service
from app.services.token_usage_service import token_usage_service
from app.services.user_key_context import UserKeyContext, create_chat_llm, format_llm_error_message

logger = get_logger(__name__)


class AgentService:
    """智能体执行服务。"""

    def __init__(self) -> None:
        self.tool_registry: dict[str, type[BaseTool]] = {
            TOOL_KNOWLEDGE_BASE: KnowledgeBaseTool,
            TOOL_TAVILY_SEARCH: TavilySearchTool,
            TOOL_PYTHON_REPL: PythonReplTool,
            TOOL_SQL_QUERY: SqlQueryTool,
            TOOL_CALCULATOR: CalculatorTool,
        }

    def register_tool(self, tool_cls: type[BaseTool]) -> None:
        """注册自定义工具类。"""
        self.tool_registry[tool_cls.name] = tool_cls
        logger.info("已注册 Agent 工具: %s", tool_cls.name)

    def list_available_tools(
        self,
        user_permissions: Optional[list[str]] = None,
    ) -> list[dict[str, str]]:
        """返回内置工具元数据列表，可按用户权限过滤。"""
        if user_permissions is None:
            return AVAILABLE_TOOL_DEFINITIONS
        return [
            item
            for item in AVAILABLE_TOOL_DEFINITIONS
            if check_tool_permission(item["name"], user_permissions)
        ]

    def _build_tool_instances(
        self,
        tool_names: list[str],
        db: AsyncSession,
        tenant_id: int,
        user: User,
        user_permissions: list[str],
        user_ctx: UserKeyContext,
    ) -> list[BaseTool]:
        """按配置实例化工具并过滤无权限工具。"""
        instances: list[BaseTool] = []
        for name in tool_names:
            if name not in self.tool_registry:
                logger.warning("未知工具名称，已跳过: %s", name)
                continue
            if not check_tool_permission(name, user_permissions):
                logger.warning("用户无权限使用工具: %s user_id=%s", name, user.id)
                continue

            tool_cls = self.tool_registry[name]
            if tool_cls is KnowledgeBaseTool:
                instances.append(KnowledgeBaseTool(db, tenant_id, user, user_ctx))
            elif tool_cls is SqlQueryTool:
                instances.append(SqlQueryTool(db, user_ctx))
            elif tool_cls is TavilySearchTool:
                instances.append(TavilySearchTool(user_ctx))
            else:
                instances.append(tool_cls())
        return instances

    @staticmethod
    def _build_args_schema(tool: BaseTool) -> type[BaseModel]:
        """将 JSON Schema 转为 Pydantic 模型供 StructuredTool 使用。"""
        properties = tool.parameters.get("properties", {})
        required_fields = set(tool.parameters.get("required", []))
        field_definitions: dict[str, Any] = {}

        for field_name, field_schema in properties.items():
            field_type: Any = str
            schema_type = field_schema.get("type")
            if schema_type == "integer":
                field_type = int
            elif schema_type == "number":
                field_type = float
            elif schema_type == "boolean":
                field_type = bool

            if field_name in required_fields:
                field_definitions[field_name] = (
                    field_type,
                    Field(description=field_schema.get("description", "")),
                )
            else:
                field_definitions[field_name] = (
                    Optional[field_type],
                    Field(default=None, description=field_schema.get("description", "")),
                )

        if not field_definitions:
            field_definitions["input"] = (str, Field(description="工具输入"))
        return create_model(f"{tool.name}_Args", **field_definitions)

    async def _execute_with_retry(
        self,
        tool: BaseTool,
        parameters: Dict[str, Any],
    ) -> ToolResult:
        """工具调用失败自动重试（最多 3 次）。"""
        max_retries = settings.agent_tool_max_retries
        timeout = settings.agent_tool_timeout_seconds
        last_error = "未知错误"

        for attempt in range(1, max_retries + 1):
            try:
                result = await asyncio.wait_for(
                    tool.execute(parameters),
                    timeout=timeout,
                )
                if result.success:
                    return result
                last_error = result.error or "工具执行失败"
            except asyncio.TimeoutError:
                last_error = f"工具调用超时（>{timeout}s）"
            except Exception as exc:
                last_error = str(exc)

            logger.warning(
                "工具执行失败，准备重试 tool=%s attempt=%s/%s error=%s",
                tool.name,
                attempt,
                max_retries,
                last_error,
            )
            if attempt < max_retries:
                await asyncio.sleep(0.5 * attempt)

        return ToolResult(success=False, content=None, error=last_error)

    def _to_langchain_tools(
        self,
        base_tools: list[BaseTool],
        user_permissions: list[str],
    ) -> list[StructuredTool]:
        """将 BaseTool 包装为 LangChain StructuredTool。"""
        lc_tools: list[StructuredTool] = []

        for base_tool in base_tools:
            # LangChain 0.1.x 要求 args_schema 为 pydantic v1 模型（见 langchain_core.pydantic_v1）
            args_schema = self._build_args_schema(base_tool)

            async def _run(
                _tool: BaseTool = base_tool,
                _user_permissions: list[str] = user_permissions,
                **kwargs: Any,
            ) -> str:
                permission_error = _tool.check_permission(_user_permissions)
                if permission_error:
                    return json.dumps(
                        {"success": False, "error": permission_error},
                        ensure_ascii=False,
                    )
                clean_kwargs = {k: v for k, v in kwargs.items() if v is not None}
                result = await self._execute_with_retry(_tool, clean_kwargs)
                if result.success:
                    if isinstance(result.content, (dict, list)):
                        return json.dumps(result.content, ensure_ascii=False)
                    return str(result.content)
                return f"工具执行失败: {result.error}"

            lc_tools.append(
                StructuredTool(
                    name=base_tool.name,
                    description=base_tool.description,
                    coroutine=_run,
                    args_schema=args_schema,
                )
            )
        return lc_tools

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """粗略估算 Token 数。"""
        return max(1, len(text) // 4)

    def _truncate_chat_history(
        self,
        chat_history: list[Any],
        max_tokens: int,
    ) -> list[Any]:
        """Token 超限保护：从最早的消息开始截断。"""
        total = sum(self._estimate_tokens(str(getattr(msg, "content", msg))) for msg in chat_history)
        trimmed = list(chat_history)

        while trimmed and total > max_tokens:
            removed = trimmed.pop(0)
            total -= self._estimate_tokens(str(getattr(removed, "content", removed)))

        return trimmed

    def _build_agent_executor(
        self,
        agent_config: Dict[str, Any],
        lc_tools: list[StructuredTool],
        user_ctx: UserKeyContext,
    ) -> AgentExecutor:
        """创建 LangChain OpenAI Tools Agent 执行器。"""
        user_ctx.get_llm_provider()
        llm = create_chat_llm(
            user_ctx,
            model_name=agent_config.get("model_name"),
            temperature=agent_config["temperature"],
            top_p=agent_config.get("top_p"),
            max_tokens=agent_config["max_tokens"],
        )

        # 使用 SystemMessage 避免 system_prompt 中的 JSON/花括号被当作模板变量
        prompt = ChatPromptTemplate.from_messages(
            [
                SystemMessage(content=agent_config["system_prompt"]),
                MessagesPlaceholder(variable_name="chat_history"),
                ("human", "{input}"),
                MessagesPlaceholder(variable_name="agent_scratchpad"),
            ]
        )

        agent = create_openai_tools_agent(llm, lc_tools, prompt)
        return AgentExecutor(
            agent=agent,
            tools=lc_tools,
            verbose=True,
            return_intermediate_steps=True,
            max_iterations=5,
            handle_parsing_errors=True,
        )

    async def run_agent(
        self,
        agent_config: Dict[str, Any],
        user_query: str,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        user_ctx: UserKeyContext,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> Dict[str, Any]:
        """非流式运行智能体。"""
        await guardrails_service.validate_user_input(user_query)
        await token_quota_service.check_tenant_quota(db, tenant_id)
        user_permissions = get_user_permissions(user)
        base_tools = self._build_tool_instances(
            agent_config.get("tools", []),
            db,
            tenant_id,
            user,
            user_permissions,
            user_ctx,
        )
        lc_tools = self._to_langchain_tools(base_tools, user_permissions)
        executor = self._build_agent_executor(agent_config, lc_tools, user_ctx)

        history_messages: list[Any] = []
        for item in chat_history or []:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                history_messages.append(AIMessage(content=content))

        history_messages = self._truncate_chat_history(
            history_messages,
            settings.agent_max_context_tokens,
        )

        result = await executor.ainvoke(
            {
                "input": user_query,
                "chat_history": history_messages,
            }
        )

        prompt_tokens = self._estimate_tokens(
            user_query + "".join(str(getattr(msg, "content", "")) for msg in history_messages)
        )
        completion_tokens = self._estimate_tokens(str(result.get("output", "")))
        await token_usage_service.record_usage(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            model_name=agent_config.get("model_name", "gpt-4o"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
        )

        return {
            "answer": result["output"],
            "intermediate_steps": [
                {
                    "tool_name": step[0].tool,
                    "tool_input": step[0].tool_input,
                    "tool_output": step[1],
                }
                for step in result.get("intermediate_steps", [])
            ],
        }

    async def run_agent_stream(
        self,
        agent_config: Dict[str, Any],
        user_query: str,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        user_ctx: UserKeyContext,
        session_id: str,
        chat_history: Optional[List[Dict[str, str]]] = None,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        流式运行智能体，推送思考状态、工具调用与回答 token。

        Yields:
            SSE 事件字典。
        """
        await guardrails_service.validate_user_input(user_query)
        await token_quota_service.check_tenant_quota(db, tenant_id)
        yield {"type": "thinking", "content": "正在分析问题..."}

        user_permissions = get_user_permissions(user)
        base_tools = self._build_tool_instances(
            agent_config.get("tools", []),
            db,
            tenant_id,
            user,
            user_permissions,
            user_ctx,
        )
        lc_tools = self._to_langchain_tools(base_tools, user_permissions)
        executor = self._build_agent_executor(agent_config, lc_tools, user_ctx)

        history_messages: list[Any] = []
        for item in chat_history or []:
            role = item.get("role")
            content = item.get("content", "")
            if role == "user":
                history_messages.append(HumanMessage(content=content))
            elif role == "assistant":
                history_messages.append(AIMessage(content=content))

        history_messages = self._truncate_chat_history(
            history_messages,
            settings.agent_max_context_tokens,
        )

        tool_label_map = {item["name"]: item["label"] for item in AVAILABLE_TOOL_DEFINITIONS}
        final_answer = ""
        intermediate_steps: list[dict[str, Any]] = []

        try:
            async for event in executor.astream_events(
                {"input": user_query, "chat_history": history_messages},
                version="v1",
            ):
                event_type = event.get("event")
                event_name = event.get("name", "")
                event_data = event.get("data", {})

                if event_type == "on_tool_start":
                    tool_name = event_name
                    tool_input = event_data.get("input", {})
                    label = tool_label_map.get(tool_name, tool_name)
                    yield {
                        "type": "tool_start",
                        "tool_name": tool_name,
                        "tool_label": label,
                        "content": f"正在调用{label}...",
                        "tool_input": tool_input,
                    }
                elif event_type == "on_tool_end":
                    tool_name = event_name
                    tool_output = event_data.get("output", "")
                    step_record = {
                        "tool_name": tool_name,
                        "tool_input": event_data.get("input", {}),
                        "tool_output": tool_output,
                    }
                    intermediate_steps.append(step_record)
                    yield {
                        "type": "tool_end",
                        "tool_name": tool_name,
                        "tool_output": tool_output,
                        "intermediate_step": step_record,
                    }
                elif event_type == "on_chat_model_end":
                    output = event_data.get("output")
                    if output is not None:
                        await token_usage_service.record_from_langchain_response(
                            db=db,
                            tenant_id=tenant_id,
                            user_id=user.id,
                            model_name=agent_config.get("model_name", "gpt-4o"),
                            response=output,
                        )
                elif event_type == "on_chat_model_stream":
                    chunk = event_data.get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        token = chunk.content
                        if isinstance(token, str) and token:
                            safe_token = await guardrails_service.sanitize_output(token)
                            final_answer += safe_token
                            yield {"type": "content", "content": safe_token}

            if not final_answer:
                # 兜底：若流式未捕获到 token，使用 invoke 获取最终答案
                result = await executor.ainvoke(
                    {"input": user_query, "chat_history": history_messages}
                )
                final_answer = result.get("output", "")
                if final_answer:
                    yield {"type": "content", "content": final_answer}
                intermediate_steps = [
                    {
                        "tool_name": step[0].tool,
                        "tool_input": step[0].tool_input,
                        "tool_output": step[1],
                    }
                    for step in result.get("intermediate_steps", [])
                ]

            await self._save_chat_messages(
                db,
                tenant_id,
                user.id,
                session_id,
                user_query,
                final_answer,
                intermediate_steps,
            )

            yield {
                "type": "done",
                "content": final_answer,
                "intermediate_steps": intermediate_steps,
                "session_id": session_id,
            }
        except Exception as exc:
            logger.error("Agent 流式执行失败: %s", exc)
            yield {"type": "error", "message": format_llm_error_message(exc)}

    async def _save_chat_messages(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        session_id: str,
        user_query: str,
        assistant_answer: str,
        intermediate_steps: list[dict[str, Any]],
    ) -> None:
        """持久化对话历史（含工具调用过程）。"""
        db.add(
            ChatHistory(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                message_type="user",
                content=user_query,
                meta_data={},
            )
        )

        for step in intermediate_steps:
            db.add(
                ChatHistory(
                    tenant_id=tenant_id,
                    user_id=user_id,
                    session_id=session_id,
                    message_type="tool",
                    content=json.dumps(step, ensure_ascii=False),
                    meta_data={
                        "tool_name": step.get("tool_name"),
                        "tool_input": step.get("tool_input"),
                    },
                )
            )

        db.add(
            ChatHistory(
                tenant_id=tenant_id,
                user_id=user_id,
                session_id=session_id,
                message_type="assistant",
                content=assistant_answer,
                meta_data={"intermediate_steps": intermediate_steps},
            )
        )
        await db.commit()

    async def get_chat_history(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        session_id: Optional[str] = None,
        agent_id: Optional[int] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询对话历史。"""
        stmt = (
            select(ChatHistory)
            .where(
                ChatHistory.tenant_id == tenant_id,
                ChatHistory.user_id == user_id,
            )
            .order_by(ChatHistory.created_at.asc())
            .limit(limit)
        )

        if session_id:
            stmt = stmt.where(ChatHistory.session_id == session_id)
        elif agent_id is not None:
            stmt = stmt.where(
                ChatHistory.session_id.like(f"agent-{agent_id}-%")
            )

        result = await db.execute(stmt)
        records = result.scalars().all()

        return [
            {
                "id": record.id,
                "session_id": record.session_id,
                "message_type": record.message_type,
                "content": record.content,
                "metadata": record.meta_data,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ]

    async def delete_chat_session(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        agent_id: int,
        session_id: str,
    ) -> int:
        """删除指定 Agent 会话的全部历史消息。"""
        if not session_id.startswith(f"agent-{agent_id}-"):
            raise ValidationError(message="会话 ID 与当前 Agent 不匹配")

        stmt = delete(ChatHistory).where(
            ChatHistory.tenant_id == tenant_id,
            ChatHistory.user_id == user_id,
            ChatHistory.session_id == session_id,
        )
        result = await db.execute(stmt)
        deleted_count = int(result.rowcount or 0)
        if deleted_count <= 0:
            raise NotFoundError(message="会话不存在或已删除")
        logger.info(
            "删除 Agent 会话历史 tenant_id=%s user_id=%s session_id=%s rows=%s",
            tenant_id,
            user_id,
            session_id,
            deleted_count,
        )
        return deleted_count

    @staticmethod
    def generate_session_id(agent_id: int) -> str:
        """生成 Agent 对话 session_id。"""
        return f"agent-{agent_id}-{uuid.uuid4().hex[:12]}"


agent_service = AgentService()
