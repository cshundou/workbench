"""
LangGraph 多智能体工作流构建器。

实现文档 5.3.2 标准拓扑：调度中心、知识库、搜索、执行、审核五个 Agent 节点，
以及文档 5.3.3 人工介入节点与 Redis 状态持久化。
"""

import asyncio
import json
import logging
import time
import operator
import re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Annotated, Any, Callable, NamedTuple, NotRequired, Optional, Sequence, TypedDict, Union

import redis
from langchain_core.messages import BaseMessage
from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.core.exceptions import ValidationError
from app.services.user_key_context import UserKeyContext, create_chat_llm
from app.services.workflow.redis_saver import RedisSaver
from app.services.workflow.workflow_agent_runner import WorkflowAgentRunner

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


def merge_tool_calls(
    left: list[dict[str, Any]],
    right: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """合并并行节点工具调用记录。"""
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
    {
        "scheduler",
        "knowledge",
        "search",
        "execution",
        "human",
        "reviewer",
        "loop",
        "condition",
        "custom_agent",
        "supervisor",
    }
)

VALID_AGENT_TYPES = frozenset({"knowledge", "search", "execution", "review"})


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
    loop_counters: dict[str, int]
    replan_count: NotRequired[int]
    node_configs: NotRequired[dict[str, dict[str, Any]]]
    tool_calls: NotRequired[Annotated[list[dict[str, Any]], merge_tool_calls]]
    loop_exit_reason: NotRequired[str]
    parallel_branch_errors: NotRequired[dict[str, str]]
    loop_conditions: NotRequired[dict[str, str]]
    tenant_id: NotRequired[int]
    user_id: NotRequired[int]


StatusCallback = Callable[[str, str, dict[str, Any]], None]
StreamCallback = Callable[[str, str], None]


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
        self._loop_node_max_iterations: dict[str, int] = {}
        self._loop_conditions: dict[str, str] = {}
        self._graph_nodes: list[dict[str, Any]] = []
        self.tenant_id: Optional[int] = None
        self.user_id: Optional[int] = None
        self.execution_id: Optional[int] = None
        self._stream_callback: Optional[StreamCallback] = None
        self._agent_runner: Optional[WorkflowAgentRunner] = None

    def set_execution_context(
        self,
        tenant_id: int,
        user_id: int,
        execution_id: Optional[int] = None,
    ) -> None:
        """设置工作流执行租户与用户上下文。"""
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.execution_id = execution_id

    def set_stream_callback(self, callback: StreamCallback) -> None:
        """设置审核节点流式输出回调。"""
        self._stream_callback = callback

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

    def _get_agent_runner(self) -> Optional[WorkflowAgentRunner]:
        """懒加载工作流 Agent 执行器。"""
        if self._agent_runner is not None:
            return self._agent_runner
        if self.tenant_id is None or self.user_id is None or self.user_ctx is None:
            return None
        self._agent_runner = WorkflowAgentRunner(
            tenant_id=self.tenant_id,
            user_id=self.user_id,
            user_ctx=self.user_ctx,
        )
        return self._agent_runner

    def _get_node_config(self, state: AgentState, node_id: str) -> dict[str, Any]:
        """读取节点 config（优先 state 快照，其次图定义）。"""
        node_configs = state.get("node_configs") or {}
        if node_id in node_configs:
            return dict(node_configs[node_id])
        for node in self._graph_nodes:
            if node.get("id") == node_id:
                return dict(node.get("config") or {})
        return {}

    def _resolve_kb_ids(self, state: AgentState, node_id: str) -> list[int]:
        """解析知识库 ID 列表：节点 config.kb_ids > 全局 kb_id。"""
        config = self._get_node_config(state, node_id)
        kb_ids_raw = config.get("kb_ids")
        if isinstance(kb_ids_raw, list) and kb_ids_raw:
            return [int(k) for k in kb_ids_raw if k is not None]
        global_kb = state.get("kb_id")
        if global_kb is not None:
            return [int(global_kb)]
        return []

    def _parse_scheduler_json(self, content: str) -> list[dict[str, Any]]:
        """从 LLM 输出解析子任务 JSON，支持代码块提取。"""
        text = content.strip()
        if text.startswith("```"):
            text = re.sub(r"^```\w*\n?", "", text)
            text = re.sub(r"\n?```$", "", text.strip())
        start = text.find("[")
        end = text.rfind("]")
        if start >= 0 and end > start:
            text = text[start : end + 1]
        parsed = json.loads(text)
        if not isinstance(parsed, list):
            raise ValueError("子任务必须为 JSON 数组")
        return parsed

    def _validate_subtasks(self, subtasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """校验并规范化子任务列表。"""
        normalized: list[dict[str, Any]] = []
        for item in subtasks:
            if not isinstance(item, dict):
                continue
            agent = item.get("agent")
            task = str(item.get("task", "")).strip()
            if agent not in VALID_AGENT_TYPES or not task:
                continue
            normalized.append({"agent": agent, "task": task, **item})
        return normalized

    def _evaluate_loop_condition(
        self,
        state: AgentState,
        node_id: str,
        condition: str,
        max_iterations: int,
    ) -> tuple[bool, str]:
        """
        判断是否满足循环退出条件。

        Returns:
            (should_exit, reason)
        """
        current_iteration = int((state.get("loop_counters") or {}).get(node_id, 0))
        if current_iteration >= max_iterations:
            return True, f"已达到最大循环次数（{max_iterations}）"

        results = state.get("results") or {}
        condition_lower = condition.lower()

        # 规则模式：结果包含关键词
        if "包含" in condition and "年" in condition:
            match = re.search(r"包含[「\"']?([^」\"'，,]+)", condition)
            keyword = match.group(1) if match else ""
            if keyword and keyword in json.dumps(results, ensure_ascii=False):
                return True, f"结果已包含「{keyword}」"

        if "为空" in condition or "无结果" in condition:
            target = "knowledge"
            if "search" in condition_lower:
                target = "search"
            value = results.get(target, "")
            if not value or "未检索" in str(value) or "未找到" in str(value):
                return False, f"{target} 结果为空，继续循环"

        # LLM 判断模式
        llm = self._create_llm()
        if llm is not None and condition.strip():
            prompt = f"""
判断以下工作流中间结果是否满足退出条件。

退出条件：{condition}

当前迭代：{current_iteration}/{max_iterations}
中间结果：
{json.dumps(results, ensure_ascii=False, default=str)}

请仅输出 JSON：{{"should_exit": true/false, "reason": "说明"}}
"""
            try:
                response = llm.invoke(prompt)
                content = response.content if isinstance(response.content, str) else str(response.content)
                payload = json.loads(content.strip().strip("`").replace("json\n", ""))
                return bool(payload.get("should_exit")), str(payload.get("reason", ""))
            except Exception as exc:
                logger.warning("循环条件 LLM 判断失败: %s", exc)

        return False, "继续执行循环体"

    def _run_role_agent(
        self,
        role: str,
        task: str,
        state: AgentState,
        node_id: str,
    ) -> dict[str, Any]:
        """通过 WorkflowAgentRunner 执行角色 Agent。"""
        runner = self._get_agent_runner()
        if runner is None:
            raise RuntimeError("未配置执行上下文或 API 密钥，无法运行 Agent")

        config = self._get_node_config(state, node_id)
        kb_id: Optional[int] = None
        if role == "knowledge":
            kb_ids = self._resolve_kb_ids(state, node_id)
            if not kb_ids:
                raise ValidationError(
                    message="知识库 Agent 需要配置 kb_id 或节点 kb_ids，请在执行时选择知识库"
                )
            kb_id = kb_ids[0]

        model_config: dict[str, Any] = {}
        if config.get("temperature") is not None:
            model_config["temperature"] = float(config["temperature"])

        return runner.run_sync(
            role=role,
            task=task,
            kb_id=kb_id,
            model_config=model_config or None,
        )

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
        workflow.add_node("supervisor", self.supervisor_node)
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
                "continue": "supervisor",
                "end": END,
            },
        )

        workflow.add_conditional_edges(
            "supervisor",
            self.route_after_supervisor,
            {
                "replan": "scheduler",
                "continue": "reviewer",
            },
        )

        workflow.add_edge("reviewer", END)

        return workflow.compile(checkpointer=self.checkpointer)

    def validate_graph_definition(self, definition: dict[str, Any]) -> None:
        """
        校验自定义工作流图定义。

        要求：有且仅有一个 scheduler 入口、节点类型合法、边引用有效。
        默认只允许 DAG；当存在 loop 节点时允许环。
        """
        nodes = definition.get("nodes") or []
        edges = definition.get("edges") or []

        if not nodes:
            raise ValidationError(message="工作流图定义不能为空")

        node_ids: set[str] = set()
        scheduler_ids: list[str] = []
        has_loop_node = False

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
            if node_type == "loop":
                has_loop_node = True

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
                if not has_loop_node:
                    raise ValidationError(
                        message="工作流图存在环，需添加 loop 节点后才允许循环"
                    )
                break

    def _parse_loop_max_iterations(self, node: dict[str, Any]) -> int:
        """解析 loop 节点最大迭代次数，默认 5。"""
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        raw_value = config.get("max_iterations", node.get("max_iterations", 5))
        try:
            parsed = int(raw_value)
            if parsed <= 0:
                return 5
            return min(parsed, 20)
        except (TypeError, ValueError):
            return 5

    def _parse_loop_condition(self, node: dict[str, Any]) -> str:
        """解析 loop 节点退出条件描述。"""
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        return str(
            config.get("loop_condition", node.get("loop_condition", "满足退出条件"))
        )

    def _build_loop_node_handler(
        self,
        node_id: str,
        max_iterations: int,
        loop_condition: str,
    ) -> Callable[[AgentState], AgentState]:
        """为指定 loop 节点构建处理函数。"""

        def _handler(state: AgentState) -> AgentState:
            return self.loop_node(
                state,
                node_id=node_id,
                max_iterations=max_iterations,
                loop_condition=loop_condition,
            )

        return _handler

    def _build_loop_router(
        self,
        node_id: str,
        max_iterations: int,
        loop_condition: str,
    ) -> Callable[[AgentState], str]:
        """为指定 loop 节点构建路由函数。"""

        def _router(state: AgentState) -> str:
            return self.route_after_loop_node(
                state,
                node_id=node_id,
                max_iterations=max_iterations,
                loop_condition=loop_condition,
            )

        return _router

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

        self._loop_node_max_iterations = {}
        self._loop_conditions = {}
        self._graph_nodes = nodes

        type_to_node_id: dict[str, str] = {}
        loop_node_ids: set[str] = set()
        condition_node_ids: set[str] = set()
        custom_agent_nodes: dict[str, int] = {}
        for node in nodes:
            node_type = node["type"]
            if node_type not in type_to_node_id:
                type_to_node_id[node_type] = node["id"]
            if node_type == "loop":
                loop_node_ids.add(node["id"])
                self._loop_node_max_iterations[node["id"]] = self._parse_loop_max_iterations(
                    node
                )
                self._loop_conditions[node["id"]] = self._parse_loop_condition(node)
            if node_type == "condition":
                condition_node_ids.add(node["id"])
            if node_type == "custom_agent":
                config = node.get("config") or {}
                agent_id = config.get("agent_id")
                if agent_id is not None:
                    custom_agent_nodes[node["id"]] = int(agent_id)

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
            "supervisor": self.supervisor_node,
            "condition": self.condition_node,
        }

        workflow = StateGraph(AgentState)
        workflow.add_node("parallel_dispatch", self.parallel_dispatch_node)
        for node in nodes:
            node_id = node["id"]
            node_type = node["type"]
            if node_type == "loop":
                max_iterations = self._loop_node_max_iterations.get(node_id, 5)
                loop_condition = self._loop_conditions.get(node_id, "满足退出条件")
                workflow.add_node(
                    node_id,
                    self._build_loop_node_handler(
                        node_id, max_iterations, loop_condition
                    ),
                )
            elif node_type == "custom_agent":
                agent_id = custom_agent_nodes.get(node_id, 0)

                def _custom_handler(
                    state: AgentState,
                    _node_id: str = node_id,
                    _agent_id: int = agent_id,
                ) -> AgentState:
                    return self.custom_agent_node(state, _node_id, _agent_id)

                workflow.add_node(node_id, _custom_handler)
            elif node_type == "condition":

                def _condition_handler(
                    state: AgentState, _node_id: str = node_id
                ) -> AgentState:
                    return self.condition_node(state, _node_id)

                workflow.add_node(node_id, _condition_handler)
            else:
                workflow.add_node(node_id, handler_map[node_type])

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

        edges_by_source: dict[str, list[str]] = {}
        for edge in edges:
            edges_by_source.setdefault(edge["source"], []).append(edge["target"])

        if human_id:
            workflow.add_edge("parallel_dispatch", human_id)
        elif reviewer_id:
            workflow.add_edge("parallel_dispatch", reviewer_id)
        else:
            workflow.add_edge("parallel_dispatch", END)

        agent_types = {"knowledge", "search", "execution"}
        for node in nodes:
            node_id = node["id"]
            if node["type"] not in agent_types:
                continue
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

        for loop_node_id in loop_node_ids:
            outgoing = edges_by_source.get(loop_node_id, [])
            if outgoing:
                continue_target = outgoing[0]
            elif human_id:
                continue_target = human_id
            elif reviewer_id:
                continue_target = reviewer_id
            else:
                continue_target = END
            max_iterations = self._loop_node_max_iterations.get(loop_node_id, 5)
            loop_condition = self._loop_conditions.get(loop_node_id, "满足退出条件")
            workflow.add_conditional_edges(
                loop_node_id,
                self._build_loop_router(
                    loop_node_id, max_iterations, loop_condition
                ),
                {
                    "continue": continue_target,
                    "end": END,
                },
            )

        supervisor_id = type_to_node_id.get("supervisor")
        if supervisor_id:
            workflow.add_conditional_edges(
                supervisor_id,
                self.route_after_supervisor,
                {
                    "replan": scheduler_id,
                    "continue": reviewer_id or human_id or END,
                },
            )

        for condition_node_id in condition_node_ids:
            node_def = next(n for n in nodes if n["id"] == condition_node_id)
            config = node_def.get("config") or {}
            branches = config.get("branches") or []
            default_target = config.get("default_target") or END
            targets: dict[str, Any] = {"end": END}
            for branch in branches:
                target = branch.get("target")
                if target:
                    targets[target] = target

            def _build_condition_router(
                _node_id: str = condition_node_id,
                _branches: list = branches,
                _default: str = default_target,
            ) -> Callable[[AgentState], str]:
                def _router(state: AgentState) -> str:
                    route_key = self.route_after_condition(
                        state, _node_id, _branches, _default
                    )
                    return route_key if route_key in targets else "end"

                return _router

            workflow.add_conditional_edges(
                condition_node_id,
                _build_condition_router(),
                targets,
            )

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

        # 监督节点触发的二次规划
        if state.get("_supervisor_need_replan"):
            incomplete = list(state.get("_supervisor_incomplete") or [])
            replan_count = int(state.get("replan_count") or 0) + 1
            state["replan_count"] = replan_count
            subtasks: list[dict[str, Any]] = []
            for agent in incomplete:
                fallback = "search" if agent == "knowledge" else agent
                subtasks.append({"agent": fallback, "task": state["task"]})
            state["subtasks"] = self._validate_subtasks(subtasks) or subtasks
            state["current_step"] = "scheduler_replanned"
            state["status"] = "running"
            state.pop("_supervisor_need_replan", None)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "subtasks": state["subtasks"],
                    "replan_count": replan_count,
                    "degraded": False,
                },
            )
            return state

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
        degraded = False
        subtasks: list[dict[str, Any]] = []
        last_error: Optional[str] = None

        try:
            if llm is not None:
                for attempt in range(3):
                    try:
                        response = llm.invoke(prompt)
                        content = response.content
                        text = content if isinstance(content, str) else str(content)
                        subtasks = self._validate_subtasks(
                            self._parse_scheduler_json(text)
                        )
                        if subtasks:
                            break
                        last_error = "子任务列表为空"
                    except Exception as parse_exc:
                        last_error = str(parse_exc)
                        logger.warning(
                            "调度拆解第%s次解析失败: %s", attempt + 1, parse_exc
                        )
                if not subtasks:
                    subtasks = self._validate_subtasks(
                        self._mock_decompose_task(state["task"])
                    )
                    degraded = True
            else:
                subtasks = self._validate_subtasks(
                    self._mock_decompose_task(state["task"])
                )
                degraded = True

            if not subtasks:
                raise ValueError(last_error or "无法拆解任务")

            state["subtasks"] = subtasks
            state["current_step"] = "scheduler_completed"
            state["status"] = "running"
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"subtasks": subtasks, "degraded": degraded},
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

        tool_calls: list[dict[str, Any]] = []
        try:
            if knowledge_task:
                query = knowledge_task.get("task", state["task"])
                run_result = self._run_role_agent("knowledge", query, state, node_id)
                result = run_result.get("answer", "")
                tool_calls = run_result.get("tool_calls", [])
                if run_result.get("error"):
                    raise RuntimeError(run_result["error"])
                state.setdefault("results", {})["knowledge"] = result
                state.setdefault("tool_calls", []).extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("knowledge"),
                    "tool_calls": tool_calls,
                },
            )
        except ValidationError as exc:
            state.setdefault("results", {})["knowledge"] = f"配置错误: {exc.message}"
            self._append_log(state, node_id, "failed", error=exc.message)
        except Exception as exc:
            logger.exception("知识库查询失败: %s", exc)
            state.setdefault("results", {})["knowledge"] = f"查询失败: {exc}"
            state.setdefault("parallel_branch_errors", {})[node_id] = str(exc)
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

        tool_calls: list[dict[str, Any]] = []
        try:
            if search_task:
                query = search_task.get("task", state["task"])
                run_result = self._run_role_agent("search", query, state, node_id)
                result = run_result.get("answer", "")
                tool_calls = run_result.get("tool_calls", [])
                state.setdefault("results", {})["search"] = result
                state.setdefault("tool_calls", []).extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("search"),
                    "tool_calls": tool_calls,
                },
            )
        except Exception as exc:
            logger.exception("联网搜索失败: %s", exc)
            state.setdefault("results", {})["search"] = f"搜索失败: {exc}"
            state.setdefault("parallel_branch_errors", {})[node_id] = str(exc)
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

        tool_calls: list[dict[str, Any]] = []
        try:
            if execution_task:
                task_desc = execution_task.get("task", state["task"])
                run_result = self._run_role_agent(
                    "execution", task_desc, state, node_id
                )
                result = run_result.get("answer", "")
                tool_calls = run_result.get("tool_calls", [])
                state.setdefault("results", {})["execution"] = result
                state.setdefault("tool_calls", []).extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("execution"),
                    "tool_calls": tool_calls,
                },
            )
        except Exception as exc:
            logger.exception("执行节点失败: %s", exc)
            state.setdefault("results", {})["execution"] = f"执行失败: {exc}"
            state.setdefault("parallel_branch_errors", {})[node_id] = str(exc)
            self._append_log(state, node_id, "failed", error=str(exc))

        return state

    def loop_node(
        self,
        state: AgentState,
        node_id: str = "loop",
        max_iterations: int = 5,
        loop_condition: str = "满足退出条件",
    ) -> AgentState:
        """循环控制节点：累计迭代次数并评估退出条件。"""
        state = dict(state)
        loop_counters = dict(state.get("loop_counters") or {})
        current_iteration = int(loop_counters.get(node_id, 0)) + 1
        loop_counters[node_id] = current_iteration
        state["loop_counters"] = loop_counters

        loop_conditions = dict(state.get("loop_conditions") or {})
        loop_conditions[node_id] = loop_condition
        state["loop_conditions"] = loop_conditions

        should_exit, reason = self._evaluate_loop_condition(
            state, node_id, loop_condition, max_iterations
        )
        if should_exit:
            state["loop_exit_reason"] = reason

        state.setdefault("results", {})["loop"] = {
            "node_id": node_id,
            "current_iteration": current_iteration,
            "max_iterations": max_iterations,
            "should_exit": should_exit,
            "reason": reason,
        }
        log_extra = {
            "loop_iteration": current_iteration,
            "max_iterations": max_iterations,
        }
        self._append_log(
            state,
            node_id,
            "running",
            input_data={
                "current_iteration": current_iteration,
                "max_iterations": max_iterations,
                "loop_condition": loop_condition,
                **log_extra,
            },
        )
        completed_log = self._append_log(
            state,
            node_id,
            "completed",
            output_data={**state["results"]["loop"], **log_extra},
        )
        completed_log.update(log_extra)
        return state

    def route_after_loop_node(
        self,
        state: AgentState,
        node_id: str = "loop",
        max_iterations: int = 5,
        loop_condition: str = "满足退出条件",
    ) -> str:
        """循环节点路由：满足条件或达到最大次数则结束，否则继续循环体。"""
        should_exit, reason = self._evaluate_loop_condition(
            state, node_id, loop_condition, max_iterations
        )
        if should_exit:
            state["loop_exit_reason"] = reason
            logger.info(
                "loop 节点退出 node_id=%s reason=%s",
                node_id,
                reason,
            )
            return "end"
        return "continue"

    def condition_node(self, state: AgentState, node_id: str = "condition") -> AgentState:
        """条件分支节点：记录当前结果供路由函数判断。"""
        state = dict(state)
        config = self._get_node_config(state, node_id)
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"results": state.get("results"), "config": config},
        )
        self._append_log(
            state,
            node_id,
            "completed",
            output_data={"results_snapshot": state.get("results")},
        )
        return state

    def route_after_condition(
        self,
        state: AgentState,
        node_id: str = "condition",
        branches: Optional[list[dict[str, Any]]] = None,
        default_target: str = "end",
    ) -> str:
        """根据规则或 LLM 选择条件分支目标节点 id。"""
        results = state.get("results") or {}
        branches = branches or []

        for branch in branches:
            condition = str(branch.get("condition", ""))
            target = str(branch.get("target", ""))
            if not target:
                continue

            # 规则：knowledge 为空
            if "knowledge" in condition and ("为空" in condition or "无结果" in condition):
                knowledge_result = str(results.get("knowledge", ""))
                if (
                    not knowledge_result
                    or "未检索" in knowledge_result
                    or "未找到" in knowledge_result
                    or "查询失败" in knowledge_result
                ):
                    return target

            # 规则：包含关键词
            if "包含" in condition:
                match = re.search(r"包含[「\"']?([^」\"'，,]+)", condition)
                keyword = match.group(1) if match else ""
                if keyword and keyword in json.dumps(results, ensure_ascii=False):
                    return target

            # LLM 模式
            llm = self._create_llm()
            if llm is not None and condition.strip():
                prompt = f"""
根据中间结果判断是否满足条件：{condition}
结果：{json.dumps(results, ensure_ascii=False, default=str)}
仅回答 yes 或 no。
"""
                try:
                    response = llm.invoke(prompt)
                    content = (
                        response.content
                        if isinstance(response.content, str)
                        else str(response.content)
                    )
                    if content.strip().lower().startswith("y"):
                        return target
                except Exception as exc:
                    logger.warning("条件分支 LLM 判断失败: %s", exc)

        return default_target if default_target else "end"

    def supervisor_node(self, state: AgentState) -> AgentState:
        """监督节点：检查子任务结果完整性，必要时触发二次规划。"""
        node_id = "supervisor"
        state = dict(state)
        results = state.get("results") or {}
        replan_count = int(state.get("replan_count") or 0)
        max_replan = settings.workflow_max_replan_count

        incomplete: list[str] = []
        for key in ("knowledge", "search", "execution"):
            value = str(results.get(key, ""))
            if any(
                subtask.get("agent") == key for subtask in state.get("subtasks", [])
            ):
                if not value or "失败" in value or "查询失败" in value:
                    incomplete.append(key)

        need_replan = bool(incomplete) and replan_count < max_replan
        self._append_log(
            state,
            node_id,
            "completed",
            output_data={
                "incomplete_agents": incomplete,
                "need_replan": need_replan,
                "replan_count": replan_count,
            },
        )
        state["current_step"] = "supervisor_checked"
        state["_supervisor_need_replan"] = need_replan
        state["_supervisor_incomplete"] = incomplete
        return state

    def route_after_supervisor(self, state: AgentState) -> str:
        """监督后路由：需要重规划则回调度，否则继续审核。"""
        if state.get("_supervisor_need_replan"):
            return "replan"
        return "continue"

    def custom_agent_node(
        self,
        state: AgentState,
        node_id: str,
        agent_id: int,
    ) -> AgentState:
        """执行用户自定义 Agent 节点。"""
        state = dict(state)
        subtask = next(
            (t for t in state.get("subtasks", []) if t.get("agent") == "custom"),
            None,
        )
        task = subtask.get("task", state["task"]) if subtask else state["task"]
        self._append_log(state, node_id, "running", input_data={"agent_id": agent_id, "task": task})

        runner = self._get_agent_runner()
        tool_calls: list[dict[str, Any]] = []
        try:
            if runner is None:
                raise RuntimeError("未配置执行上下文")
            run_result = runner.run_custom_agent_sync(agent_id, task)
            if run_result.get("error"):
                raise RuntimeError(run_result["error"])
            answer = run_result.get("answer", "")
            tool_calls = run_result.get("tool_calls", [])
            state.setdefault("results", {})[f"custom_{agent_id}"] = answer
            state.setdefault("tool_calls", []).extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"result": answer, "tool_calls": tool_calls},
            )
        except Exception as exc:
            logger.exception("自定义 Agent 节点失败: %s", exc)
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
                final_chunks: list[str] = []
                if self._stream_callback is not None:
                    for chunk in llm.stream(prompt):
                        piece = chunk.content if isinstance(chunk.content, str) else str(chunk.content)
                        if piece:
                            final_chunks.append(piece)
                            self._stream_callback(node_id, piece)
                    final_answer = "".join(final_chunks)
                else:
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
        parallel_started = time.monotonic()
        max_workers = min(
            len(handlers),
            settings.workflow_parallel_max_workers,
        )
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

        merged = self.merge_parallel_states(state, branch_states)
        parallel_duration_ms = int((time.monotonic() - parallel_started) * 1000)
        for log in merged.get("execution_logs") or []:
            if isinstance(log, dict) and log.get("status") == "completed":
                log["branch_duration_ms"] = parallel_duration_ms
        merged["parallel_duration_ms"] = parallel_duration_ms
        return merged

    def route_after_human_intervention(self, state: AgentState) -> str:
        """人工介入后的路由：未启用人工介入或已批准则继续审核，否则暂停。"""
        if not state.get("require_human_approval"):
            return "continue"
        if state.get("human_approved"):
            return "continue"
        return "end"
