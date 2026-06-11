"""
LangGraph 多智能体工作流构建器。

实现文档 5.3.2 标准拓扑：调度中心、知识库、搜索、执行、审核五个 Agent 节点，
以及文档 5.3.3 人工介入节点与 Redis 状态持久化。
"""

import asyncio
import json
import logging
import operator
import re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Any, Callable, NamedTuple, Optional, Sequence, TypedDict, Union

import redis
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.user_key_context import UserKeyContext, create_chat_llm
from app.services.workflow.redis_saver import RedisSaver

logger = logging.getLogger(__name__)

EXECUTION_TIMEOUT_SECONDS = 30


class Send(NamedTuple):
    """LangGraph Send 兼容结构，用于调度后 fan-out 并行分发。"""

    node: str
    arg: dict[str, Any]


def merge_results(left: dict[str, Any], right: dict[str, Any]) -> dict[str, Any]:
    """合并并行节点写入的 results 字段。"""
    merged = dict(left or {})
    merged.update(right or {})
    return merged


def merge_execution_logs(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """合并并行节点追加的执行日志。"""
    return list(left or []) + list(right or [])

# 标准工作流拓扑（供前端 vue-flow 渲染）
STANDARD_GRAPH_DEFINITION: dict[str, Any] = {
    "nodes": [
        {
            "id": "scheduler",
            "type": "scheduler",
            "label": "调度中心",
            "position": {"x": 400, "y": 0},
        },
        {
            "id": "knowledge_agent",
            "type": "knowledge",
            "label": "知识库 Agent",
            "position": {"x": 100, "y": 160},
        },
        {
            "id": "search_agent",
            "type": "search",
            "label": "搜索 Agent",
            "position": {"x": 300, "y": 160},
        },
        {
            "id": "execution_agent",
            "type": "execution",
            "label": "执行 Agent",
            "position": {"x": 500, "y": 160},
        },
        {
            "id": "human_intervention",
            "type": "human",
            "label": "人工介入",
            "position": {"x": 400, "y": 320},
        },
        {
            "id": "reviewer",
            "type": "reviewer",
            "label": "审核 Agent",
            "position": {"x": 400, "y": 480},
        },
    ],
    "edges": [
        {"id": "e1", "source": "scheduler", "target": "knowledge_agent"},
        {"id": "e2", "source": "scheduler", "target": "search_agent"},
        {"id": "e3", "source": "scheduler", "target": "execution_agent"},
        {"id": "e4", "source": "knowledge_agent", "target": "human_intervention"},
        {"id": "e5", "source": "search_agent", "target": "human_intervention"},
        {"id": "e6", "source": "execution_agent", "target": "human_intervention"},
        {"id": "e7", "source": "human_intervention", "target": "reviewer"},
    ],
}

NODE_LABELS: dict[str, str] = {
    node["id"]: node["label"] for node in STANDARD_GRAPH_DEFINITION["nodes"]
}

VALID_NODE_TYPES = frozenset(
    {"scheduler", "knowledge", "search", "execution", "human", "reviewer"}
)


class AgentState(TypedDict):
    """工作流全局状态（文档 5.3.2）。"""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    task: str
    subtasks: list[dict[str, Any]]
    results: Annotated[dict[str, Any], merge_results]
    current_step: str
    status: str
    error: str
    require_human_approval: bool
    human_approved: bool
    kb_id: Optional[int]
    execution_logs: Annotated[list[dict[str, Any]], merge_execution_logs]


StatusCallback = Callable[[str, str, dict[str, Any]], None]


class WorkflowBuilder:
    """LangGraph 多智能体工作流构建器。"""

    def __init__(
        self,
        redis_url: str | None = None,
        user_ctx: UserKeyContext | None = None,
    ) -> None:
        url = redis_url or settings.redis_url
        self.redis = redis.Redis.from_url(url, decode_responses=False)
        self.checkpointer = RedisSaver(self.redis)
        self._status_callback: Optional[StatusCallback] = None
        self.user_ctx = user_ctx
        # agent 类型 -> 图节点 id（build 时按 graph_definition 填充）
        self._node_id_by_agent: dict[str, str] = {
            "knowledge": "knowledge_agent",
            "search": "search_agent",
            "execution": "execution_agent",
        }

    def set_status_callback(self, callback: StatusCallback) -> None:
        """设置节点状态回调，用于 WebSocket 推送。"""
        self._status_callback = callback

    def _emit_status(
        self,
        node_id: str,
        status: str,
        log_data: dict[str, Any] | None = None,
    ) -> None:
        if self._status_callback:
            self._status_callback(node_id, status, log_data or {})

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _append_log(
        self,
        state: AgentState,
        node_id: str,
        status: str,
        input_data: dict[str, Any] | None = None,
        output_data: dict[str, Any] | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        """追加节点执行日志并触发状态回调。"""
        log_entry: dict[str, Any] = {
            "node_id": node_id,
            "node_label": NODE_LABELS.get(node_id, node_id),
            "status": status,
            "input_data": input_data,
            "output_data": output_data,
            "error": error,
            "started_at": self._now_iso() if status == "running" else None,
            "completed_at": self._now_iso()
            if status in ("completed", "failed", "waiting")
            else None,
        }
        state.setdefault("execution_logs", []).append(log_entry)
        self._emit_status(node_id, status, log_entry)
        return log_entry

    def build_standard_workflow(self, require_human: bool = False):
        """
        构建标准多智能体工作流。

        Args:
            require_human: 是否在审核前经过人工介入节点。

        Returns:
            编译后的 LangGraph 工作流。
        """
        workflow = StateGraph(AgentState)

        self._node_id_by_agent = {
            "knowledge": "knowledge_agent",
            "search": "search_agent",
            "execution": "execution_agent",
        }

        workflow.add_node("scheduler", self.scheduler_node)
        workflow.add_node("parallel_dispatch", self.parallel_dispatch_node)
        workflow.add_node("knowledge_agent", self.knowledge_agent_node)
        workflow.add_node("search_agent", self.search_agent_node)
        workflow.add_node("execution_agent", self.execution_agent_node)
        workflow.add_node("human_intervention", self.human_intervention_node)
        workflow.add_node("reviewer", self.reviewer_node)

        workflow.set_entry_point("scheduler")

        workflow.add_conditional_edges(
            "scheduler",
            self.route_after_scheduler,
            {
                "knowledge": "knowledge_agent",
                "search": "search_agent",
                "execution": "execution_agent",
                "parallel": "parallel_dispatch",
                "review": "human_intervention",
                "end": END,
            },
        )

        workflow.add_edge("parallel_dispatch", "human_intervention")

        workflow.add_edge("knowledge_agent", "human_intervention")
        workflow.add_edge("search_agent", "human_intervention")
        workflow.add_edge("execution_agent", "human_intervention")

        workflow.add_conditional_edges(
            "human_intervention",
            self.route_after_human_intervention,
            {
                "continue": "reviewer",
                "end": END,
            },
        )

        workflow.add_edge("reviewer", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def validate_graph_definition(self, definition: dict[str, Any]) -> None:
        """
        校验自定义工作流图定义。

        要求：有且仅有一个 scheduler 入口、节点类型合法、边引用有效、无环（DAG）。
        """
        nodes = definition.get("nodes") or []
        edges = definition.get("edges") or []

        if not nodes:
            raise ValidationError(message="工作流图定义不能为空")

        node_ids: set[str] = set()
        scheduler_ids: list[str] = []

        for node in nodes:
            node_id = node.get("id")
            node_type = node.get("type")
            if not node_id or not isinstance(node_id, str):
                raise ValidationError(message="节点 id 无效")
            if node_type not in VALID_NODE_TYPES:
                raise ValidationError(message=f"不支持的节点类型: {node_type}")
            if node_id in node_ids:
                raise ValidationError(message=f"重复的节点 id: {node_id}")
            node_ids.add(node_id)
            if node_type == "scheduler":
                scheduler_ids.append(node_id)

        if len(scheduler_ids) != 1:
            raise ValidationError(message="必须有且仅有一个 scheduler 入口节点")

        for edge in edges:
            source = edge.get("source")
            target = edge.get("target")
            if source not in node_ids or target not in node_ids:
                raise ValidationError(message="边引用了不存在的节点")

        adjacency: dict[str, list[str]] = {node_id: [] for node_id in node_ids}
        for edge in edges:
            adjacency[edge["source"]].append(edge["target"])

        visited: set[str] = set()
        recursion_stack: set[str] = set()

        def _has_cycle(node_id: str) -> bool:
            visited.add(node_id)
            recursion_stack.add(node_id)
            for neighbor in adjacency.get(node_id, []):
                if neighbor not in visited:
                    if _has_cycle(neighbor):
                        return True
                elif neighbor in recursion_stack:
                    return True
            recursion_stack.remove(node_id)
            return False

        for node_id in node_ids:
            if node_id not in visited and _has_cycle(node_id):
                raise ValidationError(message="工作流图存在环，仅支持 DAG")

    def build_from_definition(
        self,
        definition: dict[str, Any],
        require_human: bool = False,
    ):
        """
        根据 graph_definition 构建 LangGraph 工作流。

        无自定义定义或校验失败时由调用方回退标准拓扑。
        """
        self.validate_graph_definition(definition)

        nodes: list[dict[str, Any]] = definition["nodes"]
        edges: list[dict[str, Any]] = definition.get("edges") or []

        global NODE_LABELS
        NODE_LABELS = {
            node["id"]: node.get("label", node["id"]) for node in nodes
        }

        type_to_node_id: dict[str, str] = {}
        for node in nodes:
            node_type = node["type"]
            if node_type not in type_to_node_id:
                type_to_node_id[node_type] = node["id"]

        scheduler_id = type_to_node_id["scheduler"]
        human_id = type_to_node_id.get("human")
        reviewer_id = type_to_node_id.get("reviewer")

        self._node_id_by_agent = {
            agent: type_to_node_id[agent]
            for agent in ("knowledge", "search", "execution")
            if agent in type_to_node_id
        }

        handler_map = {
            "scheduler": self.scheduler_node,
            "knowledge": self.knowledge_agent_node,
            "search": self.search_agent_node,
            "execution": self.execution_agent_node,
            "human": self.human_intervention_node,
            "reviewer": self.reviewer_node,
        }

        workflow = StateGraph(AgentState)
        workflow.add_node("parallel_dispatch", self.parallel_dispatch_node)
        for node in nodes:
            workflow.add_node(node["id"], handler_map[node["type"]])

        workflow.set_entry_point(scheduler_id)

        scheduler_targets: dict[str, Any] = {"end": END, "parallel": "parallel_dispatch"}
        for route_key, node_type in (
            ("knowledge", "knowledge"),
            ("search", "search"),
            ("execution", "execution"),
        ):
            target_id = type_to_node_id.get(node_type)
            scheduler_targets[route_key] = target_id if target_id else END

        review_target = human_id or reviewer_id or END
        scheduler_targets["review"] = review_target

        workflow.add_conditional_edges(
            scheduler_id,
            self.route_after_scheduler,
            scheduler_targets,
        )

        if human_id:
            workflow.add_edge("parallel_dispatch", human_id)
        elif reviewer_id:
            workflow.add_edge("parallel_dispatch", reviewer_id)
        else:
            workflow.add_edge("parallel_dispatch", END)

        agent_types = {"knowledge", "search", "execution"}
        edges_by_source: dict[str, list[str]] = {}
        for edge in edges:
            edges_by_source.setdefault(edge["source"], []).append(edge["target"])

        for node in nodes:
            if node["type"] not in agent_types:
                continue
            node_id = node["id"]
            outgoing = edges_by_source.get(node_id, [])
            if outgoing:
                for target in outgoing:
                    workflow.add_edge(node_id, target)
            elif human_id:
                workflow.add_edge(node_id, human_id)
            elif reviewer_id:
                workflow.add_edge(node_id, reviewer_id)
            else:
                workflow.add_edge(node_id, END)

        if human_id:
            workflow.add_conditional_edges(
                human_id,
                self.route_after_human_intervention,
                {
                    "continue": reviewer_id or END,
                    "end": END,
                },
            )

        if reviewer_id:
            workflow.add_edge(reviewer_id, END)

        return workflow.compile(checkpointer=self.checkpointer)

    def build_workflow(
        self,
        graph_definition: dict[str, Any] | None,
        require_human: bool = False,
    ):
        """优先使用 graph_definition 构建工作流，否则回退标准拓扑。"""
        if graph_definition and graph_definition.get("nodes"):
            try:
                return self.build_from_definition(graph_definition, require_human)
            except ValidationError:
                logger.warning("自定义图定义无效，回退标准工作流拓扑")
        return self.build_standard_workflow(require_human=require_human)

    def _create_llm(self):
        """创建 LLM 实例，无用户密钥时返回 None。"""
        if self.user_ctx is None or not self.user_ctx.has_llm_key:
            return None
        try:
            return create_chat_llm(self.user_ctx, temperature=0)
        except Exception as exc:
            logger.warning("创建 LLM 失败，将使用规则降级: %s", exc)
            return None

    def scheduler_node(self, state: AgentState) -> AgentState:
        """调度中心节点：任务拆解与分配。"""
        node_id = "scheduler"
        state = dict(state)
        state.setdefault("results", {})
        state.setdefault("subtasks", [])
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"task": state.get("task")},
        )

        llm = self._create_llm()
        prompt = f"""
请将以下任务拆解为子任务，并分配给对应的智能体：
任务：{state['task']}

可用智能体：
- knowledge：查询企业内部知识库
- search：联网搜索外部信息
- execution：执行代码、计算或SQL查询
- review：汇总和审核结果

请仅输出 JSON 格式的子任务列表，例如：
[
    {{"agent": "knowledge", "task": "查询公司员工年假政策"}},
    {{"agent": "search", "task": "查询2024年法定年假天数"}}
]
"""
        try:
            if llm is not None:
                response = llm.invoke(prompt)
                content = response.content
                if isinstance(content, str):
                    subtasks = json.loads(content.strip())
                else:
                    subtasks = json.loads(str(content))
            else:
                # 无 API Key 时使用规则拆解，便于开发调试
                subtasks = self._mock_decompose_task(state["task"])

            state["subtasks"] = subtasks
            state["current_step"] = "scheduler_completed"
            state["status"] = "running"
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"subtasks": subtasks},
            )
        except Exception as exc:
            logger.exception("任务拆解失败: %s", exc)
            state["error"] = f"任务拆解失败: {exc}"
            state["status"] = "failed"
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def _mock_decompose_task(self, task: str) -> list[dict[str, Any]]:
        """无 LLM 时的默认任务拆解逻辑。"""
        subtasks: list[dict[str, Any]] = []
        lowered = task.lower()
        if any(k in task for k in ("知识", "内部", "公司", "政策", "文档")):
            subtasks.append({"agent": "knowledge", "task": task})
        if any(k in task for k in ("搜索", "联网", "外部", "最新", "2024", "2025")):
            subtasks.append({"agent": "search", "task": task})
        if any(k in lowered for k in ("计算", "代码", "sql", "执行", "统计")):
            subtasks.append({"agent": "execution", "task": task})
        if not subtasks:
            subtasks = [
                {"agent": "knowledge", "task": task},
                {"agent": "search", "task": task},
            ]
        return subtasks

    def knowledge_agent_node(self, state: AgentState) -> AgentState:
        """知识库 Agent 节点：调用 RAG 检索。"""
        node_id = "knowledge_agent"
        state = dict(state)
        knowledge_task = next(
            (t for t in state.get("subtasks", []) if t.get("agent") == "knowledge"),
            None,
        )
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"task": knowledge_task},
        )

        try:
            if knowledge_task:
                query = knowledge_task.get("task", state["task"])
                kb_id = state.get("kb_id")
                if kb_id and self.user_ctx and self.user_ctx.has_llm_key:
                    result = self._query_knowledge_base(kb_id, query)
                else:
                    result = f"[知识库模拟结果] 关于「{query}」的内部资料检索完成。"
                state.setdefault("results", {})["knowledge"] = result
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("knowledge")},
            )
        except Exception as exc:
            logger.exception("知识库查询失败: %s", exc)
            state.setdefault("results", {})["knowledge"] = f"查询失败: {exc}"
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def _query_knowledge_base(self, kb_id: int, query: str) -> str:
        """同步封装 RAG 检索（在工作流线程中调用）。"""
        import asyncio

        from app.core.database import async_session_factory
        from app.services.rag.rag_service import rag_service

        async def _search() -> str:
            async with async_session_factory() as db:
                if self.user_ctx is None:
                    return "未配置 API 密钥，无法检索知识库。"
                chunks = await rag_service.retrieve(
                    db, kb_id, query, self.user_ctx, top_k=3
                )
                if not chunks:
                    return "未检索到相关知识库内容。"
                return "\n".join(
                    c.get("content", str(c)) for c in chunks[:3]
                )

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    return pool.submit(asyncio.run, _search()).result()
            return asyncio.run(_search())
        except Exception as exc:
            logger.warning("RAG 检索异常，使用模拟结果: %s", exc)
            return f"[知识库检索] 关于「{query}」的检索结果（模拟）。"

    def search_agent_node(self, state: AgentState) -> AgentState:
        """搜索 Agent 节点：联网搜索。"""
        node_id = "search_agent"
        state = dict(state)
        search_task = next(
            (t for t in state.get("subtasks", []) if t.get("agent") == "search"),
            None,
        )
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"task": search_task},
        )

        try:
            if search_task:
                query = search_task.get("task", state["task"])
                result = self._web_search(query)
                state.setdefault("results", {})["search"] = result
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("search")},
            )
        except Exception as exc:
            logger.exception("联网搜索失败: %s", exc)
            state.setdefault("results", {})["search"] = f"搜索失败: {exc}"
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def _web_search(self, query: str) -> str:
        """调用 Tavily 搜索，失败时返回模拟结果。"""
        if self.user_ctx is None or not self.user_ctx.has_tavily_key:
            return f"[联网搜索模拟结果] 关于「{query}」的外部信息检索完成。"

        try:
            from tavily import TavilyClient

            tavily_config = self.user_ctx.get_provider("tavily")
            if tavily_config is None:
                return f"[联网搜索模拟结果] 关于「{query}」的外部信息检索完成。"

            client = TavilyClient(api_key=tavily_config.api_key)
            response = client.search(query=query, max_results=3)
            results = response.get("results", [])
            if not results:
                return "未找到相关外部信息。"
            return "\n".join(
                f"- {r.get('title', '')}: {r.get('content', '')[:200]}"
                for r in results[:3]
            )
        except Exception as exc:
            logger.warning("Tavily 搜索失败: %s", exc)
            return f"[联网搜索模拟结果] 关于「{query}」的外部信息检索完成。"

    def _resolve_execution_tool_type(self, execution_task: dict[str, Any]) -> str:
        """根据子任务配置或描述推断执行工具类型（python / sql）。"""
        tool_type = execution_task.get("tool_type")
        if tool_type in ("python", "sql"):
            return tool_type

        task_text = execution_task.get("task", "").lower()
        sql_keywords = ("sql", "select", "数据库", "查询表", "查询用户", "统计")
        if any(keyword in task_text for keyword in sql_keywords):
            return "sql"
        return "python"

    async def _generate_python_code(self, task_desc: str) -> str:
        """将自然语言任务转换为可执行 Python 代码。"""
        if any(
            keyword in task_desc
            for keyword in ("def ", "import ", "print(", "for ", "while ", "=")
        ):
            return task_desc

        llm = self._create_llm()
        if llm is None:
            return f"print({json.dumps(task_desc, ensure_ascii=False)})"

        prompt = f"""
将以下任务转换为可执行的 Python 代码，只输出代码，不要解释。
禁止使用 os、subprocess、socket 等危险模块。

任务：{task_desc}
"""
        response = llm.invoke(prompt)
        content = response.content
        code = content if isinstance(content, str) else str(content)
        if code.startswith("```"):
            code = re.sub(r"^```\w*\n?", "", code.strip())
            code = re.sub(r"\n?```$", "", code)
        return code.strip()

    def _format_execution_result(self, tool_type: str, result: Any) -> str:
        """格式化工具执行结果为工作流可读文本。"""
        content = result.content or {}
        if tool_type == "sql":
            return (
                f"SQL: {content.get('sql', '')}\n"
                f"结果 ({content.get('row_count', 0)} 行):\n"
                f"{json.dumps(content.get('rows', []), ensure_ascii=False, default=str)}"
            )
        return str(content.get("result", content))

    async def _run_execution_task_async(self, execution_task: dict[str, Any]) -> str:
        """异步调用 PythonReplTool 或 SqlQueryTool 执行子任务。"""
        from app.core.database import async_session_factory
        from app.services.agent.tools.python_repl import PythonReplTool
        from app.services.agent.tools.sql_query import SqlQueryTool

        task_desc = execution_task.get("task", "")
        tool_type = self._resolve_execution_tool_type(execution_task)

        async with async_session_factory() as db:
            if tool_type == "sql":
                if self.user_ctx is None:
                    raise RuntimeError("未配置 API 密钥，无法执行 SQL 查询")
                tool = SqlQueryTool(db, self.user_ctx)
                tool_result = await asyncio.wait_for(
                    tool.execute({"question": task_desc}),
                    timeout=EXECUTION_TIMEOUT_SECONDS,
                )
            else:
                code = await self._generate_python_code(task_desc)
                tool = PythonReplTool()
                tool_result = await asyncio.wait_for(
                    tool.execute({"code": code}),
                    timeout=EXECUTION_TIMEOUT_SECONDS,
                )

        if not tool_result.success:
            raise RuntimeError(tool_result.error or "执行工具返回失败")
        return self._format_execution_result(tool_type, tool_result)

    def _run_execution_task(self, execution_task: dict[str, Any]) -> str:
        """在同步工作流节点中运行异步执行逻辑。"""

        async def _run() -> str:
            return await self._run_execution_task_async(execution_task)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as pool:
                    future = pool.submit(asyncio.run, _run())
                    return future.result(timeout=EXECUTION_TIMEOUT_SECONDS + 5)
            return asyncio.run(_run())
        except asyncio.TimeoutError as exc:
            raise TimeoutError(f"执行超时（{EXECUTION_TIMEOUT_SECONDS}秒）") from exc

    def execution_agent_node(self, state: AgentState) -> AgentState:
        """执行 Agent 节点：调用 PythonReplTool / SqlQueryTool。"""
        node_id = "execution_agent"
        state = dict(state)
        execution_task = next(
            (t for t in state.get("subtasks", []) if t.get("agent") == "execution"),
            None,
        )
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"task": execution_task},
        )

        try:
            if execution_task:
                task_desc = execution_task.get("task", state["task"])
                result = self._run_execution_task(
                    {**execution_task, "task": task_desc},
                )
                state.setdefault("results", {})["execution"] = result
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("execution")},
            )
        except Exception as exc:
            logger.exception("执行节点失败: %s", exc)
            state["error"] = f"执行失败: {exc}"
            state.setdefault("results", {})["execution"] = f"执行失败: {exc}"
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def human_intervention_node(self, state: AgentState) -> AgentState:
        """
        人工介入节点（文档 5.3.3）。

        将工作流状态设置为等待人工确认，暂停后续审核流程。
        """
        node_id = "human_intervention"
        state = dict(state)

        if not state.get("require_human_approval"):
            return state

        state["status"] = "waiting_for_human"
        state["current_step"] = "human_intervention"
        self._append_log(
            state,
            node_id,
            "waiting",
            input_data={"results": state.get("results")},
            output_data={"message": "等待人工确认是否继续执行"},
        )
        return state

    def reviewer_node(self, state: AgentState) -> AgentState:
        """审核节点：汇总子任务结果生成最终回答。"""
        node_id = "reviewer"
        state = dict(state)
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"results": state.get("results")},
        )

        llm = self._create_llm()
        prompt = f"""
请汇总以下所有子任务的结果，生成最终回答：

原始任务：{state['task']}

子任务结果：
{json.dumps(state.get('results', {}), ensure_ascii=False, default=str)}

请生成清晰、准确、格式统一的最终回答。
"""
        try:
            if llm is not None:
                response = llm.invoke(prompt)
                content = response.content
                final_answer = content if isinstance(content, str) else str(content)
            else:
                results = state.get("results", {})
                final_answer = (
                    f"【审核汇总】\n\n原始任务：{state['task']}\n\n"
                    f"子任务结果：\n{json.dumps(results, ensure_ascii=False, indent=2)}"
                )

            state.setdefault("results", {})["final"] = final_answer
            state["status"] = "completed"
            state["current_step"] = "reviewer_completed"
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"final": final_answer},
            )
        except Exception as exc:
            logger.exception("审核节点失败: %s", exc)
            state["error"] = f"审核失败: {exc}"
            state["status"] = "failed"
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def fan_out_after_scheduler(
        self, state: AgentState
    ) -> Union[list[Send], str]:
        """
        调度后 fan-out：返回 Send 列表触发并行 Agent，或单路由键 / end。
        """
        if state.get("status") == "failed":
            return "end"

        sends = self._build_parallel_sends(state)
        if not sends:
            return "review"
        if len(sends) == 1:
            agent_type = next(
                (
                    agent
                    for agent, node_id in self._node_id_by_agent.items()
                    if node_id == sends[0].node
                ),
                None,
            )
            if agent_type:
                return agent_type
        return "parallel"

    def route_after_scheduler(self, state: AgentState) -> str:
        """调度后的路由逻辑（兼容 fan_out_after_scheduler）。"""
        result = self.fan_out_after_scheduler(state)
        if isinstance(result, str):
            return result
        return "parallel"

    def _build_parallel_sends(self, state: AgentState) -> list[Send]:
        """根据子任务构建 LangGraph Send 列表。"""
        subtasks = state.get("subtasks", [])
        state_snapshot = dict(state)
        sends: list[Send] = []
        for agent_type, node_id in self._node_id_by_agent.items():
            if any(task.get("agent") == agent_type for task in subtasks):
                sends.append(Send(node_id, state_snapshot))
        return sends

    def _agent_handler_for_node(self, node_id: str) -> Optional[Callable[[AgentState], AgentState]]:
        """按节点 id 解析 Agent 处理函数。"""
        reverse_map = {v: k for k, v in self._node_id_by_agent.items()}
        agent_type = reverse_map.get(node_id)
        handler_map: dict[str, Callable[[AgentState], AgentState]] = {
            "knowledge": self.knowledge_agent_node,
            "search": self.search_agent_node,
            "execution": self.execution_agent_node,
        }
        if agent_type is None:
            return None
        return handler_map.get(agent_type)

    def merge_parallel_states(
        self,
        base_state: AgentState,
        branch_states: list[AgentState],
    ) -> AgentState:
        """合并并行分支状态（results / execution_logs）。"""
        merged = dict(base_state)
        merged_results: dict[str, Any] = dict(base_state.get("results") or {})
        merged_logs: list[dict[str, Any]] = list(base_state.get("execution_logs") or [])

        for branch in branch_states:
            merged_results.update(branch.get("results") or {})
            merged_logs.extend(branch.get("execution_logs") or [])
            if branch.get("error"):
                merged["error"] = branch["error"]
            if branch.get("status") == "failed":
                merged["status"] = "failed"

        merged["results"] = merged_results
        merged["execution_logs"] = merged_logs
        return merged

    def parallel_dispatch_node(self, state: AgentState) -> AgentState:
        """
        并行调度节点：按 Send 语义 fan-out 执行多个 Agent（langgraph 0.0.26 兼容实现）。
        """
        sends = self._build_parallel_sends(state)
        if not sends:
            return state

        handlers: list[tuple[str, Callable[[AgentState], AgentState]]] = []
        for send in sends:
            handler = self._agent_handler_for_node(send.node)
            if handler is not None:
                handlers.append((send.node, handler))

        if not handlers:
            return state

        branch_states: list[AgentState] = []
        max_workers = min(len(handlers), 3)
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = {
                pool.submit(handler, dict(send.arg)): node_id
                for node_id, handler in handlers
                for send in sends
                if send.node == node_id
            }
            for future in as_completed(futures):
                try:
                    branch_states.append(future.result())
                except Exception as exc:
                    logger.exception("并行节点执行失败: %s", exc)
                    failed_state = dict(state)
                    failed_state["status"] = "failed"
                    failed_state["error"] = f"并行执行失败: {exc}"
                    branch_states.append(failed_state)

        return self.merge_parallel_states(state, branch_states)

    def route_after_human_intervention(self, state: AgentState) -> str:
        """人工介入后的路由：未启用人工介入或已批准则继续审核，否则暂停。"""
        if not state.get("require_human_approval"):
            return "continue"
        if state.get("human_approved"):
            return "continue"
        return "end"
