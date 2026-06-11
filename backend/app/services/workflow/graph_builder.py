"""
LangGraph 多智能体工作流构建器。

实现文档 5.3.2 标准拓扑：调度中心、知识库、搜索、执行、审核五个 Agent 节点，
以及文档 5.3.3 人工介入节点与 Redis 状态持久化。
"""

import json
import logging
import operator
from datetime import datetime, timezone
from typing import Annotated, Any, Callable, Optional, Sequence, TypedDict

import redis
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.user_key_context import UserKeyContext, create_chat_llm
from app.services.workflow.redis_saver import RedisSaver

logger = logging.getLogger(__name__)

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


class AgentState(TypedDict):
    """工作流全局状态（文档 5.3.2）。"""

    messages: Annotated[Sequence[BaseMessage], operator.add]
    task: str
    subtasks: list[dict[str, Any]]
    results: dict[str, Any]
    current_step: str
    status: str
    error: str
    require_human_approval: bool
    human_approved: bool
    kb_id: Optional[int]
    execution_logs: list[dict[str, Any]]


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

        workflow.add_node("scheduler", self.scheduler_node)
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
                "review": "human_intervention",
                "end": END,
            },
        )

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
        self._append_log(node_id, "running", input_data={"task": state.get("task")})
        state = dict(state)
        state.setdefault("results", {})
        state.setdefault("subtasks", [])

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
                node_id,
                "completed",
                output_data={"subtasks": subtasks},
            )
        except Exception as exc:
            logger.exception("任务拆解失败: %s", exc)
            state["error"] = f"任务拆解失败: {exc}"
            state["status"] = "failed"
            self._append_log(node_id, "failed", error=str(exc))

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
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("knowledge")},
            )
        except Exception as exc:
            logger.exception("知识库查询失败: %s", exc)
            state.setdefault("results", {})["knowledge"] = f"查询失败: {exc}"
            self._append_log(node_id, "failed", error=str(exc))

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
        self._append_log(node_id, "running", input_data={"task": search_task})

        try:
            if search_task:
                query = search_task.get("task", state["task"])
                result = self._web_search(query)
                state.setdefault("results", {})["search"] = result
            self._append_log(
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("search")},
            )
        except Exception as exc:
            logger.exception("联网搜索失败: %s", exc)
            state.setdefault("results", {})["search"] = f"搜索失败: {exc}"
            self._append_log(node_id, "failed", error=str(exc))

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

    def execution_agent_node(self, state: AgentState) -> AgentState:
        """执行 Agent 节点：代码与计算执行。"""
        node_id = "execution_agent"
        state = dict(state)
        execution_task = next(
            (t for t in state.get("subtasks", []) if t.get("agent") == "execution"),
            None,
        )
        self._append_log(node_id, "running", input_data={"task": execution_task})

        try:
            if execution_task:
                task_desc = execution_task.get("task", state["task"])
                result = f"[执行模拟结果] 已完成任务「{task_desc}」的计算与处理。"
                state.setdefault("results", {})["execution"] = result
            self._append_log(
                node_id,
                "completed",
                output_data={"result": state.get("results", {}).get("execution")},
            )
        except Exception as exc:
            logger.exception("执行节点失败: %s", exc)
            state.setdefault("results", {})["execution"] = f"执行失败: {exc}"
            self._append_log(node_id, "failed", error=str(exc))

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
                node_id,
                "completed",
                output_data={"final": final_answer},
            )
        except Exception as exc:
            logger.exception("审核节点失败: %s", exc)
            state["error"] = f"审核失败: {exc}"
            state["status"] = "failed"
            self._append_log(node_id, "failed", error=str(exc))

        return state

    def route_after_scheduler(self, state: AgentState) -> str:
        """调度后的路由逻辑。"""
        if state.get("status") == "failed":
            return "end"

        subtasks = state.get("subtasks", [])
        if any(t.get("agent") == "knowledge" for t in subtasks):
            return "knowledge"
        if any(t.get("agent") == "search" for t in subtasks):
            return "search"
        if any(t.get("agent") == "execution" for t in subtasks):
            return "execution"
        return "review"

    def route_after_human_intervention(self, state: AgentState) -> str:
        """人工介入后的路由：未启用人工介入或已批准则继续审核，否则暂停。"""
        if not state.get("require_human_approval"):
            return "continue"
        if state.get("human_approved"):
            return "continue"
        return "end"
