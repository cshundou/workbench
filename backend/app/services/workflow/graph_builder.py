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
from app.services.workflow.nodes.audit_node import (
    DEFAULT_AUDIT_DIMENSIONS,
    ForcedAuditRunner,
)
from app.services.workflow.nodes.constants import (
    AGENT_ROLES,
    MAX_REVIEW_RETRIES,
    NODE_GROUP_CHAT_ROLE,
    SUBTASK_ROLE_MAP,
)
from app.services.workflow.nodes.group_chat_subtasks import (
    build_final_answer,
    calc_group_chat_progress,
    enrich_subtasks_from_team_config,
    enrich_subtasks_with_roles,
    get_next_phase,
    get_pending_subtask,
    has_pending_in_phase,
    mark_subtask_completed,
)
from app.services.workflow.team_builder import TeamBuilder
from app.services.delivery.ppt_generator_service import ppt_generator_service
from app.services.delivery.ppt_outline_builder import build_ppt_outline
from app.services.delivery.task_intent import detect_delivery_format
from app.services.workflow.role_catalog import (
    AUDIT_REJECT_ROLE_MAP,
    ROLE_AGENT_TYPE_MAP,
    build_role_lookup,
)
from app.services.workflow.hybrid_checkpoint import create_checkpointer
from app.services.workflow.redis_saver import RedisSaver
from app.services.workflow.workflow_tracing import record_workflow_node_span
from app.services.workflow.tool_manager import WorkflowToolManager
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


def _ensure_dict(state: dict[str, Any], key: str) -> dict[str, Any]:
    """确保 state[key] 为 dict，避免 checkpoint/Redis 中 null 导致下标赋值异常。"""
    value = state.get(key)
    if not isinstance(value, dict):
        state[key] = {}
    return state[key]


def _ensure_list(state: dict[str, Any], key: str) -> list[Any]:
    """确保 state[key] 为 list。"""
    value = state.get(key)
    if not isinstance(value, list):
        state[key] = []
    return state[key]


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
        "audit",
        "skill",
        "loop",
        "condition",
        "custom_agent",
        "supervisor",
        "sub_workflow",
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
    # 群聊协同扩展字段（统一引擎复用）
    deliverables: NotRequired[list[dict[str, Any]]]
    review_count: NotRequired[int]
    review_result: NotRequired[Optional[dict[str, Any]]]
    final_answer: NotRequired[str]
    current_subtask_index: NotRequired[int]
    user_supplements: NotRequired[list[str]]
    progress: NotRequired[float]
    human_reject_target: NotRequired[str]
    human_rejected: NotRequired[bool]
    human_intervention_records: NotRequired[list[dict[str, Any]]]
    # 节点路由辅助字段（须声明在 State 内，禁止以下划线临时键写入 state）
    gc_audit_retry: NotRequired[bool]
    audit_retry: NotRequired[bool]
    supervisor_need_replan: NotRequired[bool]
    supervisor_incomplete: NotRequired[list[str]]
    team_config: NotRequired[dict[str, Any]]
    reject_info: NotRequired[dict[str, Any]]
    current_phase: NotRequired[int]
    workflow_phases: NotRequired[list[dict[str, Any]]]
    gc_tier_route: NotRequired[str]


StatusCallback = Callable[[str, str, dict[str, Any]], None]
StreamCallback = Callable[[str, str], None]
GroupChatCallback = Callable[[dict[str, Any]], None]

# 向后兼容：从 nodes.constants 重导出
__all_node_role_map__ = NODE_GROUP_CHAT_ROLE


class WorkflowBuilder:
    """LangGraph 多智能体工作流构建器。"""

    def __init__(
        self,
        redis_url: str | None = None,
        user_ctx: UserKeyContext | None = None,
    ) -> None:
        url = redis_url or settings.redis_url
        self.redis = redis.Redis.from_url(url, decode_responses=False)
        self.checkpointer = create_checkpointer(self.redis)
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
        self._group_chat_callback: Optional[GroupChatCallback] = None
        self._member_status_callback: Optional[Callable[[str, str], None]] = None
        self._supplement_loader: Optional[Callable[[], list[str]]] = None
        self._agent_runner: Optional[WorkflowAgentRunner] = None
        self._tool_manager: Optional[WorkflowToolManager] = None
        self._trace_id: Optional[str] = None
        self._team_config: dict[str, Any] = {}

    def set_team_config(self, team_config: dict[str, Any]) -> None:
        """设置动态团队配置。"""
        self._team_config = team_config or {}

    def _get_role_info(self, role: str, state: AgentState | None = None) -> dict[str, str]:
        """获取角色展示信息（支持动态团队）。"""
        members = self._team_config.get("members")
        if state and not members:
            members = (state.get("team_config") or {}).get("members")
        lookup = build_role_lookup(members)
        return lookup.get(role, AGENT_ROLES.get(role, AGENT_ROLES["project_manager"]))

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

    def set_group_chat_callback(self, callback: GroupChatCallback) -> None:
        """设置群聊消息回调，用于群聊视图实时展示工作流过程。"""
        self._group_chat_callback = callback

    def set_member_status_callback(
        self, callback: Callable[[str, str], None]
    ) -> None:
        """设置群聊成员状态回调。"""
        self._member_status_callback = callback

    def set_supplement_loader(self, loader: Callable[[], list[str]]) -> None:
        """设置用户补充要求加载器。"""
        self._supplement_loader = loader

    def set_trace_id(self, trace_id: Optional[str]) -> None:
        """设置全链路 TraceID。"""
        self._trace_id = trace_id

    def _emit_group_chat(
        self,
        node_id: str,
        message_type: str,
        content: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        """向群聊视图推送标准化消息（WorkflowBuilder 节点钩子）。"""
        if not self._group_chat_callback:
            return

        role = NODE_GROUP_CHAT_ROLE.get(node_id, "project_manager")
        role_info = AGENT_ROLES.get(role, AGENT_ROLES["project_manager"])
        payload: dict[str, Any] = {
            "id": f"wf-{node_id}-{int(time.time() * 1000)}",
            "timestamp": self._now_iso(),
            "sender": {
                "id": role_info["id"],
                "name": role_info["name"],
                "role": role,
                "avatar": role_info["avatar"],
            },
            "type": message_type,
            "content": content,
            "attachments": attachments or [],
            "metadata": metadata or {"node_id": node_id},
        }
        self._group_chat_callback(payload)

    def _set_member_status(self, role: str, status: str) -> None:
        if self._member_status_callback:
            self._member_status_callback(role, status)

    def _emit_group_chat_role(
        self,
        role: str,
        message_type: str,
        content: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        receiver: str | None = None,
    ) -> None:
        """按群聊角色推送消息。"""
        if not self._group_chat_callback:
            return
        import uuid

        role_info = self._get_role_info(role)
        payload: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": self._now_iso(),
            "sender": {
                "id": role_info.get("id", role),
                "name": role_info.get("name", role),
                "role": role,
                "avatar": role_info.get("avatar", "🤖"),
            },
            "receiver": receiver,
            "type": message_type,
            "content": content,
            "attachments": attachments or [],
            "metadata": metadata or {},
        }
        self._group_chat_callback(payload)

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
        _ensure_list(state, "execution_logs").append(log_entry)
        self._emit_status(node_id, status, log_entry)
        if status in ("completed", "failed", "waiting"):
            record_workflow_node_span(
                self._trace_id,
                self.tenant_id,
                node_id,
                status,
                log_entry,
            )
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

    def _get_tool_manager(self) -> Optional[WorkflowToolManager]:
        """懒加载统一工具管理器。"""
        runner = self._get_agent_runner()
        if runner is None or self.tenant_id is None or self.user_id is None:
            return None
        if self.user_ctx is None:
            return None
        if self._tool_manager is None:
            self._tool_manager = WorkflowToolManager(
                tenant_id=self.tenant_id,
                user_id=self.user_id,
                user_ctx=self.user_ctx,
                runner=runner,
            )
        return self._tool_manager

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
        """通过 WorkflowToolManager 统一执行角色 Agent（内置 + Skill/MCP）。"""
        tool_manager = self._get_tool_manager()
        if tool_manager is None:
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

        result = tool_manager.run_role_agent(
            role=role,
            task=task,
            node_config=config,
            kb_id=kb_id,
            model_config=model_config or None,
            max_iterations=int(config.get("max_iterations", 5)),
        )
        if result.get("error"):
            raise RuntimeError(result["error"])
        return result

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
            self._build_human_intervention_router("supervisor", "scheduler"),
            {
                "continue": "supervisor",
                "reject": "scheduler",
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

    def sub_workflow_node(
        self,
        state: AgentState,
        node_id: str,
        sub_config: dict[str, Any],
    ) -> AgentState:
        """子流程节点：嵌入并执行另一个工作流，独立日志与版本锁定。"""
        state = dict(state)
        workflow_id = sub_config.get("workflow_id")
        locked_version = sub_config.get("version")
        self._append_log(
            state,
            node_id,
            "running",
            input_data={
                "workflow_id": workflow_id,
                "version": locked_version,
                "task": state.get("task"),
            },
        )
        try:
            if not workflow_id:
                raise ValidationError(message="子流程节点未配置 workflow_id")
            result = self._invoke_sub_workflow(
                int(workflow_id),
                str(state.get("task", "")),
                locked_version,
                state,
            )
            _ensure_dict(state, "results")[node_id] = result.get("output", "")
            _ensure_dict(state, "sub_workflow_logs")[node_id] = result.get("logs", [])
            self._append_log(
                state,
                node_id,
                "completed",
                output_data=result,
            )
        except Exception as exc:
            logger.exception("子流程执行失败 node=%s: %s", node_id, exc)
            _ensure_dict(state, "results")[node_id] = f"子流程失败: {exc}"
            self._append_log(state, node_id, "failed", error=str(exc))
        return state

    def _invoke_sub_workflow(
        self,
        workflow_id: int,
        task: str,
        version: Optional[str],
        parent_state: AgentState,
    ) -> dict[str, Any]:
        """同步调用嵌套工作流（在线程池中执行异步逻辑）。"""
        import asyncio
        from concurrent.futures import ThreadPoolExecutor

        async def _run() -> dict[str, Any]:
            from app.core.database import async_session_factory
            from app.models.workflow import Workflow
            from app.models.workflow_version import WorkflowVersion
            from sqlalchemy import select

            async with async_session_factory() as db:
                wf_stmt = select(Workflow).where(Workflow.id == workflow_id)
                workflow = (await db.execute(wf_stmt)).scalar_one_or_none()
                if workflow is None:
                    return {"output": "子工作流不存在", "logs": []}

                graph_def = workflow.graph_definition
                if version:
                    ver_stmt = select(WorkflowVersion).where(
                        WorkflowVersion.workflow_id == workflow_id,
                        WorkflowVersion.version == version,
                    )
                    ver = (await db.execute(ver_stmt)).scalar_one_or_none()
                    if ver:
                        graph_def = ver.graph_definition

                if self.user_ctx is None:
                    return {"output": "未配置 API 密钥", "logs": []}

                builder = WorkflowBuilder(settings.redis_url, user_ctx=self.user_ctx)
                graph = builder.build_workflow(graph_def)
                sub_state: dict[str, Any] = {
                    "messages": [],
                    "task": task,
                    "subtasks": [],
                    "results": {},
                    "current_step": "init",
                    "status": "running",
                    "error": "",
                    "kb_id": parent_state.get("kb_id"),
                    "execution_logs": [],
                    "loop_counters": {},
                }
                final = graph.invoke(sub_state)
                logs = list(final.get("execution_logs") or [])
                output = final.get("results", {}).get("review") or str(
                    final.get("results", {})
                )
                return {"output": output, "logs": logs, "version": version}

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with ThreadPoolExecutor(max_workers=1) as pool:
                    return pool.submit(asyncio.run, _run()).result()
            return asyncio.run(_run())
        except RuntimeError:
            return asyncio.run(_run())

    def _parse_loop_max_iterations(self, node: dict[str, Any]) -> int:
        """解析 loop 节点最大迭代次数，默认 10。"""
        config = node.get("config") if isinstance(node.get("config"), dict) else {}
        raw_value = config.get("max_iterations", node.get("max_iterations", 10))
        try:
            parsed = int(raw_value)
            if parsed <= 0:
                return 10
            return min(parsed, 20)
        except (TypeError, ValueError):
            return 10

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
        sub_workflow_nodes: dict[str, dict[str, Any]] = {}
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
            if node_type == "sub_workflow":
                config = node.get("config") or {}
                wf_id = config.get("workflow_id")
                if wf_id is not None:
                    sub_workflow_nodes[node["id"]] = {
                        "workflow_id": int(wf_id),
                        "version": config.get("version"),
                    }

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
            elif node_type == "sub_workflow":
                sub_cfg = sub_workflow_nodes.get(node_id, {})

                def _sub_workflow_handler(
                    state: AgentState,
                    _node_id: str = node_id,
                    _cfg: dict[str, Any] = sub_cfg,
                ) -> AgentState:
                    return self.sub_workflow_node(state, _node_id, _cfg)

                workflow.add_node(node_id, _sub_workflow_handler)
            elif node_type == "audit":

                def _audit_handler(
                    state: AgentState, _node_id: str = node_id
                ) -> AgentState:
                    return self.forced_audit_node(state, _node_id)

                workflow.add_node(node_id, _audit_handler)
            elif node_type == "skill":

                def _skill_handler(
                    state: AgentState, _node_id: str = node_id
                ) -> AgentState:
                    return self.skill_call_node(state, _node_id)

                workflow.add_node(node_id, _skill_handler)
            else:
                handler = handler_map.get(node_type)
                if handler is None:
                    raise ValidationError(message=f"未知节点类型: {node_type}")
                workflow.add_node(node_id, handler)

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
            reject_target = scheduler_id
            workflow.add_conditional_edges(
                human_id,
                self._build_human_intervention_router(
                    reviewer_id or END, reject_target
                ),
                {
                    "continue": reviewer_id or END,
                    "reject": reject_target,
                    "end": END,
                },
            )

        if reviewer_id:
            workflow.add_edge(reviewer_id, END)

        return workflow.compile(checkpointer=self.checkpointer)

    def build_group_chat_workflow(self):
        """
        构建群聊协同标准工作流（分阶段统筹 + 单步执行 + 审核闸门）。

        拓扑：初始化 → 阶段计划 → 单个子任务 → 阶段小结 →（循环）→ 终审 → 人工兜底。
        """
        workflow = StateGraph(AgentState)
        workflow.add_node("gc_init", self.group_chat_init_node)
        workflow.add_node("gc_plan", self.group_chat_plan_node)
        workflow.add_node("gc_subtasks", self.group_chat_subtasks_node)
        workflow.add_node("gc_tier_review", self.group_chat_tier_review_node)
        workflow.add_node("gc_audit", self.group_chat_audit_node)
        workflow.add_node("gc_human", self.group_chat_human_node)

        workflow.set_entry_point("gc_init")
        workflow.add_edge("gc_init", "gc_plan")
        workflow.add_edge("gc_plan", "gc_subtasks")
        workflow.add_edge("gc_subtasks", "gc_tier_review")
        workflow.add_conditional_edges(
            "gc_tier_review",
            self.route_after_group_chat_tier,
            {
                "continue_tier": "gc_subtasks",
                "next_phase": "gc_plan",
                "audit": "gc_audit",
            },
        )
        workflow.add_conditional_edges(
            "gc_audit",
            self.route_after_group_chat_audit,
            {
                "retry": "gc_subtasks",
                "human": "gc_human",
                "end": END,
            },
        )
        workflow.add_edge("gc_human", END)
        return workflow.compile(checkpointer=self.checkpointer)

    def build_dynamic_group_chat_workflow(
        self, team_config: dict[str, Any] | None = None
    ):
        """
        构建动态团队群聊工作流。

        基于团队配置动态生成子任务与执行链路，图拓扑保持固定以避免递归问题。
        """
        if team_config:
            self.set_team_config(team_config)
        return self.build_group_chat_workflow()

    def group_chat_init_node(self, state: AgentState) -> AgentState:
        """群聊初始化：任务拆解并生成带角色的子任务列表。"""
        state = dict(state)
        _ensure_list(state, "deliverables")
        _ensure_dict(state, "results")
        if not isinstance(state.get("review_count"), int):
            state["review_count"] = 0
        _ensure_list(state, "user_supplements")

        if self._supplement_loader:
            loaded = self._supplement_loader()
            if loaded:
                state["user_supplements"].extend(loaded)

        supplements = state.get("user_supplements") or []
        if supplements:
            latest = supplements[-1]
            self._emit_group_chat_role(
                "project_manager",
                "task_assignment",
                f"收到用户补充要求，已转发给团队：{latest}",
            )
            state["user_supplements"] = []

        self._set_member_status("project_manager", "thinking")

        team_config = state.get("team_config") or self._team_config

        if not state.get("subtasks"):
            self._emit_group_chat_role(
                "project_manager",
                "task_start",
                f"收到任务！我来拆解并分配给团队成员：\n\n**{state['task']}**",
            )
            if team_config and team_config.get("members"):
                subtasks = enrich_subtasks_from_team_config(team_config, state["task"])
            else:
                agent_state = self.scheduler_node(state)
                if agent_state.get("status") == "failed":
                    state["status"] = "failed"
                    state["error"] = agent_state.get("error", "任务拆解失败")
                    self._emit_group_chat_role("project_manager", "error", state["error"])
                    self._set_member_status("project_manager", "completed")
                    return state
                raw = agent_state.get("subtasks", [])
                subtasks = enrich_subtasks_with_roles(raw, state["task"])

            state["subtasks"] = subtasks
            state["status"] = "running"
            state["progress"] = 10.0
            phases = (team_config or {}).get("workflow_phases")
            if not phases:
                phases = TeamBuilder.build_workflow_phases(
                    (team_config or {}).get("members", [])
                )
            state["workflow_phases"] = phases
            state["current_phase"] = 1
            delivery_format = (team_config or {}).get("delivery_format") or detect_delivery_format(
                state["task"]
            )
            state["delivery_format"] = delivery_format
            self._emit_group_chat_role(
                "project_manager",
                "task_assignment",
                "任务已拆解为分阶段计划，将按阶段统筹推进（非一次性并行分配）。",
                metadata={"workflow_phases": phases},
            )

        if state.get("current_phase") is None:
            state["current_phase"] = 1
        self._set_member_status("project_manager", "completed")
        return state

    def group_chat_plan_node(self, state: AgentState) -> AgentState:
        """统筹节点：发布当前阶段计划，仅激活本阶段子任务。"""
        state = dict(state)
        current_phase = int(state.get("current_phase") or 1)
        phases = state.get("workflow_phases") or []
        phase_label = next(
            (p.get("label") for p in phases if p.get("phase") == current_phase),
            f"阶段 {current_phase}",
        )
        subtasks = state.get("subtasks", [])
        phase_tasks = [
            s for s in subtasks if int(s.get("phase") or 2) == current_phase
        ]
        lookup = build_role_lookup(
            (state.get("team_config") or self._team_config or {}).get("members")
        )
        lines = [
            f"- {lookup.get(s['role'], {}).get('name', s['role'])}：{s.get('task', '')[:60]}"
            for s in phase_tasks
            if s.get("status") != "completed"
        ]
        self._set_member_status("project_manager", "thinking")
        self._emit_group_chat_role(
            "project_manager",
            "phase_start",
            f"进入 **{phase_label}**\n\n本阶段任务：\n" + ("\n".join(lines) or "- 无待办"),
            metadata={"phase": current_phase, "phase_label": phase_label},
        )
        self._set_member_status("project_manager", "completed")
        return state

    def group_chat_subtasks_node(self, state: AgentState) -> AgentState:
        """群聊子任务：每图步仅执行一个就绪子任务（阶段 + 依赖约束）。"""
        state = dict(state)
        _ensure_list(state, "deliverables")
        _ensure_dict(state, "results")

        current_phase = int(state.get("current_phase") or 1)
        pending = get_pending_subtask(state.get("subtasks", []), current_phase=current_phase)
        if pending is None:
            return state

        role = pending.get("role", "researcher")
        agent_type = pending.get("agent", "search")
        task_desc = pending.get("task", state["task"])
        subtask_id = pending.get("id", "")

        self._set_member_status(role, "thinking")
        self._set_member_status(role, "working")
        self._emit_group_chat_role(
            role,
            "progress_update",
            f"收到，开始处理：{task_desc}",
            metadata={"task_id": subtask_id, "phase": current_phase},
        )
        started = time.monotonic()
        role_agent = ROLE_AGENT_TYPE_MAP.get(role, agent_type)

        try:
            if role_agent == "analysis" or role in (
                "analyst",
                "financial_analyst",
                "copywriter",
                "content_editor",
                "data_visualizer",
                "ppt_designer",
                "compliance_officer",
            ):
                result = self._run_analyst_subtask(state, task_desc, role=role)
                result_key = "analysis"
            elif agent_type == "knowledge":
                run_result = self._run_role_agent(
                    "knowledge", task_desc, state, "knowledge_agent"
                )
                result = run_result.get("answer", "")
                result_key = "knowledge"
            elif agent_type == "search":
                run_result = self._run_role_agent(
                    "search", task_desc, state, "search_agent"
                )
                result = run_result.get("answer", "")
                result_key = "search"
            else:
                run_result = self._run_role_agent(
                    "execution", task_desc, state, "execution_agent"
                )
                result = run_result.get("answer", "")
                result_key = "execution"

            duration_ms = int((time.monotonic() - started) * 1000)
            attachments = self._build_subtask_attachments(result_key, result)
            self._emit_group_chat_role(
                role,
                "result_delivery",
                f"任务完成！{task_desc[:50]}...",
                attachments=attachments,
                metadata={"task_id": subtask_id, "duration": duration_ms},
            )
            _ensure_dict(state, "results")[result_key] = result
            _ensure_list(state, "deliverables").append(
                {
                    "role": role,
                    "task_id": subtask_id,
                    "content": result,
                    "attachments": attachments,
                }
            )
            mark_subtask_completed(state["subtasks"], subtask_id)
            role_name = self._get_role_info(role, state).get("name", role)
            self._emit_group_chat_role(
                role,
                "answer",
                f"【{role_name}】任务「{task_desc[:30]}」已完成，请查收。",
                receiver="project_manager",
            )
        except Exception as exc:
            logger.exception("群聊子任务失败 role=%s: %s", role, exc)
            self._set_member_status(role, "error")
            self._emit_group_chat_role(role, "error", f"任务执行失败：{exc}")
            for subtask in state.get("subtasks", []):
                if subtask.get("id") == subtask_id:
                    subtask["status"] = "error"
                    break
        else:
            self._set_member_status(role, "completed")

        state["progress"] = calc_group_chat_progress(
            state.get("subtasks", []), state.get("status", "running")
        )
        return state

    def group_chat_tier_review_node(self, state: AgentState) -> AgentState:
        """阶段小结：PM 汇总本阶段产出，决定继续本阶段 / 进入下一阶段 / 提交终审。"""
        state = dict(state)
        current_phase = int(state.get("current_phase") or 1)
        subtasks = state.get("subtasks", [])

        if has_pending_in_phase(subtasks, current_phase):
            state["gc_tier_route"] = "continue_tier"
            return state

        phase_deliverables = [
            d
            for d in state.get("deliverables", [])
            if any(
                s.get("id") == d.get("task_id")
                and int(s.get("phase") or 2) == current_phase
                for s in subtasks
            )
        ]
        summary = "\n".join(
            f"- {d.get('role')}: {str(d.get('content', ''))[:120]}..."
            for d in phase_deliverables[:5]
        ) or "本阶段暂无新增交付物。"
        phases = state.get("workflow_phases") or []
        phase_label = next(
            (p.get("label") for p in phases if p.get("phase") == current_phase),
            f"阶段 {current_phase}",
        )
        self._emit_group_chat_role(
            "project_manager",
            "phase_summary",
            f"**{phase_label}** 已完成。\n\n阶段要点：\n{summary}",
            metadata={"phase": current_phase},
        )

        next_phase = get_next_phase(subtasks, current_phase)
        if next_phase is not None:
            state["current_phase"] = next_phase
            state["gc_tier_route"] = "next_phase"
        else:
            state["status"] = "reviewing"
            state["gc_tier_route"] = "audit"
            self._emit_group_chat_role(
                "project_manager",
                "review_request",
                "全部阶段已完成，提交审核员进行最终审核。",
            )
        state["progress"] = calc_group_chat_progress(
            subtasks, state.get("status", "running")
        )
        return state

    def route_after_group_chat_tier(self, state: AgentState) -> str:
        """阶段小结后的路由。"""
        route = state.get("gc_tier_route") or "audit"
        if route in ("continue_tier", "next_phase", "audit"):
            return route
        return "audit"

    def _run_analyst_subtask(
        self,
        state: AgentState,
        task_desc: str,
        *,
        role: str = "analyst",
    ) -> str:
        """分析师/文案/PPT 设计师子任务：基于已有结果生成报告或幻灯片大纲。"""
        results = state.get("results", {})
        llm = self._create_llm()
        delivery_format = state.get("delivery_format") or detect_delivery_format(state["task"])
        if delivery_format == "ppt" and role == "ppt_designer":
            analysis_prompt = f"""
请作为 PPT 设计师，基于以下资料完成演示文稿结构化方案并准备生成文件：

原始任务：{state['task']}
设计要求：{task_desc}

已有资料：
{json.dumps(results, ensure_ascii=False, default=str)}

请输出 JSON（不要其他说明），结构如下：
```json
{{
  "title": "演示标题",
  "subtitle": "副标题",
  "template_id": "business_minimal",
  "slides": [
    {{"slide_type": "cover", "title": "标题", "subtitle": "副标题"}},
    {{"slide_type": "toc", "title": "目录", "bullets": ["章节1", "章节2"]}},
    {{"slide_type": "content", "title": "章节", "bullets": ["要点1", "要点2"]}},
    {{"slide_type": "section", "title": "过渡页标题", "subtitle": "说明"}},
    {{"slide_type": "content", "title": "数据页", "bullets": ["结论"], "chart": {{"chart_type": "bar", "categories": ["A","B"], "series": [{{"name": "指标", "values": [1,2]}}]}}}},
    {{"slide_type": "ending", "title": "谢谢聆听"}}
  ]
}}
```
要求：8-15 页，template_id 选 business_minimal 或 tech_modern，内容专业简洁。
"""
        elif delivery_format == "ppt":
            analysis_prompt = f"""
请作为文案策划师，基于以下资料完成演示文稿（PPT）大纲撰写：

原始任务：{state['task']}
撰写要求：{task_desc}

已有资料：
{json.dumps(results, ensure_ascii=False, default=str)}

请输出 JSON 格式的幻灯片大纲（不要其他说明文字），结构如下：
```json
{{
  "title": "演示标题",
  "slides": [
    {{"slide_type": "content", "title": "章节标题", "bullets": ["要点1", "要点2", "要点3"]}}
  ]
}}
```
要求：5-12 页幻灯片，每页 3-5 条要点，语言简洁专业。
"""
        else:
            analysis_prompt = f"""
请基于以下资料完成数据分析与报告撰写：

原始任务：{state['task']}
分析要求：{task_desc}

已有资料：
{json.dumps(results, ensure_ascii=False, default=str)}

请输出结构化的分析报告，包含关键发现、数据摘要和建议。
"""
        if llm is not None:
            response = llm.invoke(analysis_prompt)
            content = response.content
            return content if isinstance(content, str) else str(content)
        if delivery_format == "ppt":
            return json.dumps(
                {
                    "slides": [
                        {"title": state["task"][:40], "bullets": ["多 Agent 协同生成"]},
                        {
                            "title": "资料摘要",
                            "bullets": [
                                str(v)[:100]
                                for v in list(results.values())[:5]
                            ]
                            or ["暂无资料"],
                        },
                    ]
                },
                ensure_ascii=False,
            )
        return (
            f"【分析报告】\n\n任务：{task_desc}\n\n"
            f"数据摘要：\n{json.dumps(results, ensure_ascii=False, indent=2)}"
        )

    def _generate_ppt_deliverable(self, state: AgentState) -> dict[str, Any] | None:
        """审核通过后生成 PPTX 文件。"""
        if self.tenant_id is None or self.execution_id is None:
            logger.warning("缺少 tenant/session 上下文，跳过 PPT 生成")
            return None
        try:
            outline = build_ppt_outline(
                state["task"],
                state.get("deliverables", []),
            )
            result = ppt_generator_service.generate_pptx(
                self.tenant_id,
                self.execution_id,
                outline,
            )
            return {
                "filename": result["filename"],
                "file_path": result["file_path"],
                "size": result["size"],
                "slide_count": result["slide_count"],
                "template_id": result.get("template_id", "business_minimal"),
                "download_path": (
                    f"/api/v1/group-chat/sessions/{self.execution_id}"
                    f"/deliverables/{result['filename']}"
                ),
            }
        except Exception as exc:
            logger.exception("PPT 生成失败: %s", exc)
            return None

    @staticmethod
    def _build_subtask_attachments(
        result_key: str, result: str
    ) -> list[dict[str, Any]]:
        """构造子任务交付附件。"""
        if result_key == "execution" and result:
            return [
                {
                    "type": "code",
                    "name": "执行结果",
                    "content": result,
                    "language": "python",
                }
            ]
        if result_key in ("knowledge", "search") and result:
            return [{"type": "text", "name": "检索结果", "content": result}]
        if result_key == "analysis" and result:
            return [
                {
                    "type": "chart",
                    "name": "分析图表",
                    "content": {"type": "bar", "summary": result[:200]},
                },
                {"type": "text", "name": "分析报告", "content": result},
            ]
        return []

    def _resolve_audit_assignee(
        self,
        review_result: dict[str, Any],
        state: AgentState,
    ) -> str:
        """精准打回：根据审核维度定位负责角色。"""
        assignee = review_result.get("assignee", "analyst")
        team_members = (state.get("team_config") or self._team_config).get("members", [])
        team_role_ids = {
            m.get("role_id") or m.get("role") for m in team_members
        }
        # 根据未通过的审核维度映射打回目标
        dimensions = review_result.get("dimensions") or {}
        for dim_key, passed in dimensions.items():
            if passed:
                continue
            mapped = AUDIT_REJECT_ROLE_MAP.get(dim_key)
            if mapped and (not team_role_ids or mapped in team_role_ids):
                return mapped
        # 根据问题描述关键词匹配
        issues_text = " ".join(review_result.get("issues") or [])
        keyword_map = {
            "数据": "engineer",
            "资料": "researcher",
            "逻辑": "analyst",
            "格式": "content_editor",
            "版式": "ppt_designer",
            "排版": "ppt_designer",
            "视觉": "ppt_designer",
            "PPT": "ppt_designer",
            "幻灯片": "ppt_designer",
            "合规": "compliance_officer",
        }
        for kw, role in keyword_map.items():
            if kw in issues_text and (not team_role_ids or role in team_role_ids):
                return role
        if team_role_ids and assignee not in team_role_ids:
            for candidate in ("ppt_designer", "analyst", "engineer", "researcher", "copywriter"):
                if candidate in team_role_ids:
                    return candidate
        lookup = build_role_lookup(team_members)
        if assignee not in lookup:
            assignee = "analyst"
        return assignee

    def group_chat_audit_node(self, state: AgentState) -> AgentState:
        """群聊强制审核节点（复用通用审核能力）。"""
        state = dict(state)
        review_count = int(state.get("review_count") or 0)
        self._set_member_status("auditor", "working")
        delivery_format = state.get("delivery_format") or detect_delivery_format(state["task"])
        audit_msg = (
            "开始审核最终成果，将从完整性、版式视觉、逻辑合理性等维度评估..."
            if delivery_format == "ppt"
            else "开始审核最终成果，将从完整性、数据准确性、逻辑合理性、合规性四个维度评估..."
        )
        self._emit_group_chat_role(
            "auditor",
            "progress_update",
            audit_msg,
        )

        llm = self._create_llm()

        def _invoke(prompt: str) -> str:
            if llm is None:
                return ""
            response = llm.invoke(prompt)
            content = response.content
            return content if isinstance(content, str) else str(content)

        audit_runner = ForcedAuditRunner(llm_invoke=_invoke if llm else None)
        audit_config: dict[str, Any] = {}
        if delivery_format == "ppt":
            from app.services.workflow.nodes.audit_node import PPT_AUDIT_DIMENSIONS

            audit_config["audit_dimensions"] = PPT_AUDIT_DIMENSIONS
        review_result = audit_runner.run(
            task=state["task"],
            deliverables=state.get("deliverables", []),
            results=state.get("results", {}),
            config=audit_config,
        )
        state["review_result"] = review_result

        if review_result.get("passed"):
            final_answer = build_final_answer(
                state["task"],
                state.get("deliverables", []),
                review_result,
                state.get("team_config") or self._team_config,
            )
            state["final_answer"] = final_answer
            state["status"] = "completed"
            state["progress"] = 100.0
            delivery_format = state.get("delivery_format") or detect_delivery_format(
                state["task"]
            )
            task_attachments: list[dict[str, Any]] = [
                {"type": "text", "name": "最终报告", "content": final_answer},
            ]
            ppt_file = None
            if delivery_format == "ppt":
                ppt_file = self._generate_ppt_deliverable(state)
                if ppt_file:
                    state["ppt_file"] = ppt_file
                    task_attachments.append(
                        {
                            "type": "file",
                            "name": ppt_file["filename"],
                            "content": ppt_file["download_path"],
                            "file_type": "pptx",
                            "size": ppt_file["size"],
                            "slide_count": ppt_file["slide_count"],
                            "template_id": ppt_file.get("template_id"),
                        }
                    )
            self._emit_group_chat_role(
                "auditor",
                "review_result",
                f"✅ 审核通过！{review_result.get('summary', '')}",
                metadata={"review": review_result},
            )
            complete_msg = "🎉 所有审核通过，任务完成！最终交付物如下："
            if ppt_file:
                complete_msg += f"\n\n📎 演示文稿已生成：**{ppt_file['filename']}**（{ppt_file['slide_count']} 页）"
            self._emit_group_chat_role(
                "project_manager",
                "task_complete",
                complete_msg,
                attachments=task_attachments,
                metadata={"ppt_file": ppt_file} if ppt_file else None,
            )
            self._set_member_status("auditor", "idle")
            return state

        review_count += 1
        state["review_count"] = review_count
        issues = review_result.get("issues") or ["成果未达标准"]
        issue_text = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(issues))
        max_retries = MAX_REVIEW_RETRIES

        if review_count >= max_retries:
            state["status"] = "human_review"
            state["error"] = f"审核员连续{max_retries}次审核不通过，已转人工审核"
            self._emit_group_chat_role(
                "auditor",
                "review_result",
                f"❌ 第{review_count}次审核不通过，已达最大打回次数。\n{issue_text}\n\n已提交人工审核。",
                metadata={"review": review_result, "human_review": True},
            )
            self._set_member_status("auditor", "idle")
            return state

        assignee = self._resolve_audit_assignee(review_result, state)
        for subtask in state.get("subtasks", []):
            if subtask.get("role") == assignee:
                subtask["status"] = "pending"
                subtask["task"] = (
                    f"【修改】{'; '.join(issues[:2])} — {subtask.get('task', '')}"
                )
                break
        state["status"] = "running"
        state["gc_audit_retry"] = True
        state["reject_info"] = {
            "assignee": assignee,
            "reason": "; ".join(issues[:2]),
            "round": review_count,
        }
        self._set_member_status(assignee, "revision")
        self._emit_group_chat_role(
            "auditor",
            "review_result",
            f"❌ 审核不通过（第{review_count}次），已打回给"
            f"{self._get_role_info(assignee, state).get('name', assignee)}：\n{issue_text}",
            metadata={"review": review_result, "assignee": assignee, "retry": review_count},
        )
        self._set_member_status("auditor", "completed")
        return state

    def route_after_group_chat_audit(self, state: AgentState) -> str:
        """群聊审核后路由。"""
        if state.get("status") == "completed":
            return "end"
        if state.get("status") == "human_review":
            return "human"
        if state.get("status") == "failed":
            return "end"
        if state.get("gc_audit_retry"):
            state.pop("gc_audit_retry", None)
            return "retry"
        return "end"

    def group_chat_human_node(self, state: AgentState) -> AgentState:
        """群聊人工审核等待节点。"""
        state = dict(state)
        state["status"] = "human_review"
        state["require_human_approval"] = True
        self._append_log(
            state,
            "gc_human",
            "waiting",
            output_data={"message": "等待人工审核"},
        )
        return state

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
        """创建 LLM 实例（含运行时故障降级），无用户密钥时返回 None。"""
        if self.user_ctx is None or not self.user_ctx.has_llm_key:
            return None
        try:
            from app.services.llm_fallback_service import llm_fallback_service

            primary_config = self.user_ctx.get_llm_provider()
            primary_model = primary_config.model_name or "gpt-4o-mini"
            llm, _, _ = llm_fallback_service.create_llm_with_fallback(
                self.user_ctx,
                model_name=primary_model,
                temperature=0,
                top_p=None,
                max_tokens=None,
            )
            return llm
        except Exception as exc:
            logger.warning("创建 LLM 失败，将使用规则降级: %s", exc)
            return None

    def scheduler_node(self, state: AgentState) -> AgentState:
        """调度中心节点：任务拆解与分配。"""
        node_id = "scheduler"
        state = dict(state)
        _ensure_dict(state, "results")
        _ensure_list(state, "subtasks")

        # 监督节点触发的二次规划
        if state.get("supervisor_need_replan"):
            incomplete = list(state.get("supervisor_incomplete") or [])
            replan_count = int(state.get("replan_count") or 0) + 1
            state["replan_count"] = replan_count
            subtasks: list[dict[str, Any]] = []
            for agent in incomplete:
                fallback = "search" if agent == "knowledge" else agent
                subtasks.append({"agent": fallback, "task": state["task"]})
            state["subtasks"] = self._validate_subtasks(subtasks) or subtasks
            state["current_step"] = "scheduler_replanned"
            state["status"] = "running"
            state.pop("supervisor_need_replan", None)
            state.pop("supervisor_incomplete", None)
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
            lines = [
                f"{idx + 1}. {item.get('agent', '')}: {item.get('task', '')}"
                for idx, item in enumerate(subtasks)
            ]
            self._emit_group_chat(
                node_id,
                "task_assignment",
                "任务拆解完成：\n" + "\n".join(lines),
                metadata={"subtasks": subtasks, "degraded": degraded},
            )
        except Exception as exc:
            logger.exception("任务拆解失败: %s", exc)
            state["error"] = f"任务拆解失败: {exc}"
            state["status"] = "failed"
            self._append_log(state, node_id, "failed", error=str(exc))
            self._emit_group_chat(node_id, "error", f"任务拆解失败: {exc}")

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
                _ensure_dict(state, "results")["knowledge"] = result
                _ensure_list(state, "tool_calls").extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("knowledge"),
                    "tool_calls": tool_calls,
                },
            )
            result_text = str(state.get("results", {}).get("knowledge", ""))
            self._emit_group_chat(
                node_id,
                "result_delivery",
                "知识库检索完成",
                attachments=[{"type": "text", "name": "检索结果", "content": result_text}],
                metadata={"tool_calls": tool_calls},
            )
        except ValidationError as exc:
            _ensure_dict(state, "results")["knowledge"] = f"配置错误: {exc.message}"
            self._append_log(state, node_id, "failed", error=exc.message)
            self._emit_group_chat(node_id, "error", f"知识库配置错误: {exc.message}")
        except Exception as exc:
            logger.exception("知识库查询失败: %s", exc)
            _ensure_dict(state, "results")["knowledge"] = f"查询失败: {exc}"
            _ensure_dict(state, "parallel_branch_errors")[node_id] = str(exc)
            self._append_log(state, node_id, "failed", error=str(exc))
            self._emit_group_chat(node_id, "error", f"知识库查询失败: {exc}")

        return state

    def _query_knowledge_base(self, kb_id: int, query: str) -> str:
        """同步封装 RAG 检索（在工作流线程中调用）。"""
        from app.services.rag.rag_service import rag_service
        from app.utils.async_runner import ephemeral_db_session, run_coro_in_fresh_loop

        async def _search() -> str:
            async with ephemeral_db_session() as db:
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
            return run_coro_in_fresh_loop(_search())
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
                _ensure_dict(state, "results")["search"] = result
                _ensure_list(state, "tool_calls").extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("search"),
                    "tool_calls": tool_calls,
                },
            )
            result_text = str(state.get("results", {}).get("search", ""))
            self._emit_group_chat(
                node_id,
                "result_delivery",
                "联网搜索完成",
                attachments=[{"type": "text", "name": "搜索结果", "content": result_text}],
                metadata={"tool_calls": tool_calls},
            )
        except Exception as exc:
            logger.exception("联网搜索失败: %s", exc)
            _ensure_dict(state, "results")["search"] = f"搜索失败: {exc}"
            _ensure_dict(state, "parallel_branch_errors")[node_id] = str(exc)
            self._append_log(state, node_id, "failed", error=str(exc))
            self._emit_group_chat(node_id, "error", f"联网搜索失败: {exc}")

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
                _ensure_dict(state, "results")["execution"] = result
                _ensure_list(state, "tool_calls").extend(tool_calls)
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "result": state.get("results", {}).get("execution"),
                    "tool_calls": tool_calls,
                },
            )
            result_text = str(state.get("results", {}).get("execution", ""))
            self._emit_group_chat(
                node_id,
                "result_delivery",
                "代码执行完成",
                attachments=[
                    {
                        "type": "code",
                        "name": "执行结果",
                        "content": result_text,
                        "language": "python",
                    }
                ],
                metadata={"tool_calls": tool_calls},
            )
        except Exception as exc:
            logger.exception("执行节点失败: %s", exc)
            _ensure_dict(state, "results")["execution"] = f"执行失败: {exc}"
            _ensure_dict(state, "parallel_branch_errors")[node_id] = str(exc)
            self._append_log(state, node_id, "failed", error=str(exc))
            self._emit_group_chat(node_id, "error", f"代码执行失败: {exc}")

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

        _ensure_dict(state, "results")["loop"] = {
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
        state["supervisor_need_replan"] = need_replan
        state["supervisor_incomplete"] = incomplete
        return state

    def route_after_supervisor(self, state: AgentState) -> str:
        """监督后路由：需要重规划则回调度，否则继续审核。"""
        if state.get("supervisor_need_replan"):
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
            _ensure_dict(state, "results")[f"custom_{agent_id}"] = answer
            _ensure_list(state, "tool_calls").extend(tool_calls)
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

        将工作流状态设置为等待人工确认；支持 approve 续跑与 reject 打回指定节点。
        """
        node_id = "human_intervention"
        state = dict(state)

        if not state.get("require_human_approval"):
            return state

        # 已批准或已驳回打回：透传状态，由路由决定下一节点
        if state.get("human_approved"):
            state["status"] = "running"
            state["human_rejected"] = False
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"message": "人工审核已通过，继续执行"},
            )
            return state
        if state.get("human_rejected"):
            state["status"] = "running"
            state["human_approved"] = False
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={
                    "message": "人工审核已驳回，打回重做",
                    "reject_target": state.get("human_reject_target"),
                },
            )
            return state

        state["status"] = "waiting_for_human"
        state["current_step"] = "human_intervention"
        config = self._get_node_config(state, node_id)
        state["human_reject_target"] = str(
            config.get("reject_target", config.get("reject_target_node", "scheduler"))
        )
        self._append_log(
            state,
            node_id,
            "waiting",
            input_data={"results": state.get("results")},
            output_data={
                "message": "等待人工确认是否继续执行",
                "reject_target": state.get("human_reject_target"),
            },
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

            _ensure_dict(state, "results")["final"] = final_answer
            state["status"] = "completed"
            state["current_step"] = "reviewer_completed"
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"final": final_answer},
            )
            self._emit_group_chat(
                node_id,
                "review_result",
                "✅ 审核汇总完成，最终成果已生成",
                attachments=[{"type": "text", "name": "最终报告", "content": final_answer}],
            )
        except Exception as exc:
            logger.exception("审核节点失败: %s", exc)
            state["error"] = f"审核失败: {exc}"
            state["status"] = "failed"
            self._append_log(state, node_id, "failed", error=str(exc))
            self._emit_group_chat(node_id, "error", f"审核失败: {exc}")

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
        """
        合并并行分支状态（results / execution_logs）。

        单个分支失败不影响其他分支；仅当全部分支失败时才标记整体 failed。
        """
        merged = dict(base_state)
        merged_results: dict[str, Any] = dict(base_state.get("results") or {})
        merged_logs: list[dict[str, Any]] = list(base_state.get("execution_logs") or [])
        merged_errors: dict[str, str] = dict(base_state.get("parallel_branch_errors") or {})

        failed_branch_count = 0
        for branch in branch_states:
            merged_results.update(branch.get("results") or {})
            merged_logs.extend(branch.get("execution_logs") or [])
            merged_errors.update(branch.get("parallel_branch_errors") or {})
            if branch.get("status") == "failed":
                failed_branch_count += 1

        merged["results"] = merged_results
        merged["execution_logs"] = merged_logs
        merged["parallel_branch_errors"] = merged_errors

        if branch_states and failed_branch_count == len(branch_states):
            merged["status"] = "failed"
            merged["error"] = "所有并行分支均执行失败"
        elif failed_branch_count > 0:
            # 部分分支失败：保留成功结果，继续后续审核节点
            merged["status"] = merged.get("status") or "running"

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
                node_id = futures[future]
                try:
                    branch_states.append(future.result())
                except Exception as exc:
                    logger.exception("并行节点执行失败 node=%s: %s", node_id, exc)
                    failed_state: AgentState = dict(state)
                    _ensure_dict(failed_state, "parallel_branch_errors")[node_id] = str(
                        exc
                    )
                    branch_states.append(failed_state)

        merged = self.merge_parallel_states(state, branch_states)
        parallel_duration_ms = int((time.monotonic() - parallel_started) * 1000)
        for log in merged.get("execution_logs") or []:
            if isinstance(log, dict) and log.get("status") == "completed":
                log["branch_duration_ms"] = parallel_duration_ms
        merged["parallel_duration_ms"] = parallel_duration_ms
        return merged

    def route_after_human_intervention(self, state: AgentState) -> str:
        """人工介入后的路由：未启用/已批准继续；打回则跳转；否则暂停。"""
        if not state.get("require_human_approval"):
            return "continue"
        if state.get("human_approved"):
            return "continue"
        if state.get("human_rejected"):
            return "reject"
        return "end"

    def _build_human_intervention_router(
        self,
        continue_target: str,
        default_reject_target: str,
    ) -> Callable[[AgentState], str]:
        """构建人工介入条件路由（支持打回指定节点）。"""

        def _router(state: AgentState) -> str:
            route = self.route_after_human_intervention(state)
            if route == "continue":
                return "continue"
            if route == "reject":
                return "reject"
            return "end"

        return _router

    def forced_audit_node(
        self,
        state: AgentState,
        node_id: str = "forced_audit",
    ) -> AgentState:
        """通用强制审核节点：四维度审核、结构化存储、打回与人工兜底。"""
        state = dict(state)
        config = self._get_node_config(state, node_id)
        max_retries = int(config.get("max_review_retries", MAX_REVIEW_RETRIES))
        review_count = int(state.get("review_count") or 0)

        self._append_log(
            state,
            node_id,
            "running",
            input_data={"deliverables": state.get("deliverables", [])},
        )

        llm = self._create_llm()

        def _invoke(prompt: str) -> str:
            if llm is None:
                return ""
            response = llm.invoke(prompt)
            content = response.content
            return content if isinstance(content, str) else str(content)

        deliverables = state.get("deliverables") or [
            {"role": k, "content": v}
            for k, v in (state.get("results") or {}).items()
        ]
        audit_runner = ForcedAuditRunner(llm_invoke=_invoke if llm else None)
        review_result = audit_runner.run(
            task=state["task"],
            deliverables=deliverables,
            results=state.get("results", {}),
            config=config,
        )
        state["review_result"] = review_result
        _ensure_list(state, "human_intervention_records").append(
            {
                "type": "audit",
                "node_id": node_id,
                "review": review_result,
                "review_count": review_count + (0 if review_result.get("passed") else 1),
            }
        )

        if review_result.get("passed"):
            final_answer = build_final_answer(
                state["task"],
                deliverables,
                review_result,
            )
            _ensure_dict(state, "results")["final"] = final_answer
            state["final_answer"] = final_answer
            state["status"] = "completed"
            self._append_log(
                state,
                node_id,
                "completed",
                output_data={"review": review_result, "final": final_answer},
            )
            self._emit_group_chat(
                node_id,
                "review_result",
                f"✅ 审核通过！{review_result.get('summary', '')}",
                metadata={"review": review_result},
            )
            return state

        review_count += 1
        state["review_count"] = review_count
        reject_target = str(
            config.get("reject_target", config.get("reject_target_node", "scheduler"))
        )
        state["human_reject_target"] = reject_target

        if review_count >= max_retries:
            state["status"] = "waiting_for_human"
            state["require_human_approval"] = True
            state["error"] = f"审核连续{max_retries}次不通过，转人工介入"
            self._append_log(
                state,
                node_id,
                "waiting",
                output_data={"review": review_result, "human_review": True},
            )
            return state

        state["status"] = "audit_rejected"
        state["audit_retry"] = True
        self._append_log(
            state,
            node_id,
            "completed",
            output_data={
                "review": review_result,
                "retry": review_count,
                "reject_target": reject_target,
            },
        )
        return state

    def route_after_forced_audit(
        self,
        state: AgentState,
        reject_target: str = "scheduler",
    ) -> str:
        """强制审核节点路由。"""
        if state.get("status") == "completed":
            return "end"
        if state.get("status") == "waiting_for_human":
            return "human"
        if state.get("audit_retry"):
            state.pop("audit_retry", None)
            return "retry"
        return "end"

    def skill_call_node(self, state: AgentState, node_id: str) -> AgentState:
        """Skill 调用节点：在工作流中直接执行指定 Skill。"""
        state = dict(state)
        config = self._get_node_config(state, node_id)
        skill_key = str(config.get("skill_key", "")).strip()
        if not skill_key:
            self._append_log(state, node_id, "failed", error="未配置 skill_key")
            return state

        task = str(config.get("task") or state.get("task", ""))
        self._append_log(
            state,
            node_id,
            "running",
            input_data={"skill_key": skill_key, "task": task},
        )

        tool_manager = self._get_tool_manager()
        if tool_manager is None:
            self._append_log(state, node_id, "failed", error="未配置执行上下文")
            return state

        run_result = tool_manager.run_skill(skill_key, task, node_config=config)
        if run_result.get("error"):
            self._append_log(state, node_id, "failed", error=run_result["error"])
            return state

        answer = run_result.get("answer", "")
        _ensure_dict(state, "results")[f"skill_{skill_key}"] = answer
        _ensure_list(state, "tool_calls").extend(run_result.get("tool_calls", []))
        self._append_log(
            state,
            node_id,
            "completed",
            output_data={"skill_key": skill_key, "result": answer},
        )
        return state
