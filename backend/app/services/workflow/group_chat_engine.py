"""
群聊式多 Agent 协同 LangGraph 引擎。

基于现有 WorkflowBuilder 扩展，将工作流执行过程转化为
标准化群聊消息流，并实现五角色协同与强制审核环节。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, NotRequired, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.core.config import settings
from app.services.user_key_context import UserKeyContext
from app.services.workflow.graph_builder import WorkflowBuilder
from app.services.workflow.redis_saver import RedisSaver

logger = logging.getLogger(__name__)

MAX_REVIEW_RETRIES = 3

# 标准五角色定义
AGENT_ROLES: dict[str, dict[str, str]] = {
    "project_manager": {
        "id": "project_manager",
        "name": "项目经理",
        "avatar": "👨‍💼",
        "color": "#1677FF",
    },
    "researcher": {
        "id": "researcher",
        "name": "研究员",
        "avatar": "🔍",
        "color": "#00B42A",
    },
    "engineer": {
        "id": "engineer",
        "name": "工程师",
        "avatar": "💻",
        "color": "#722ED1",
    },
    "analyst": {
        "id": "analyst",
        "name": "分析师",
        "avatar": "📊",
        "color": "#FF7D00",
    },
    "auditor": {
        "id": "auditor",
        "name": "审核员",
        "avatar": "✅",
        "color": "#F53F3F",
    },
}

# 子任务 agent 类型到群聊角色的映射
SUBTASK_ROLE_MAP: dict[str, str] = {
    "knowledge": "researcher",
    "search": "researcher",
    "execution": "engineer",
    "analysis": "analyst",
}

PROGRESS_STEPS: list[dict[str, str]] = [
    {"key": "decompose", "label": "任务拆解"},
    {"key": "research", "label": "资料检索"},
    {"key": "engineering", "label": "工程实现"},
    {"key": "analysis", "label": "数据分析"},
    {"key": "review", "label": "成果审核"},
    {"key": "delivery", "label": "最终交付"},
]

MessageCallback = Callable[[dict[str, Any]], None]
MemberStatusCallback = Callable[[str, str], None]
SupplementLoader = Callable[[], list[str]]


class GroupChatState(TypedDict):
    """群聊协同 LangGraph 状态。"""

    task: str
    kb_id: Optional[int]
    subtasks: list[dict[str, Any]]
    results: dict[str, Any]
    deliverables: list[dict[str, Any]]
    status: str
    progress: float
    current_step: int
    current_subtask_index: int
    review_count: int
    review_result: Optional[dict[str, Any]]
    user_supplements: list[str]
    error: str
    final_answer: str
    member_statuses: dict[str, str]
    node_configs: NotRequired[dict[str, dict[str, Any]]]
    _reject_assignee: NotRequired[str]


class GroupChatEngine:
    """群聊式多 Agent 协同引擎。"""

    def __init__(
        self,
        redis_url: str | None = None,
        user_ctx: UserKeyContext | None = None,
    ) -> None:
        self._builder = WorkflowBuilder(redis_url=redis_url, user_ctx=user_ctx)
        self._message_callback: Optional[MessageCallback] = None
        self._member_status_callback: Optional[MemberStatusCallback] = None
        self._supplement_loader: Optional[SupplementLoader] = None
        self.session_id: Optional[int] = None
        self.tenant_id: Optional[int] = None
        self.user_id: Optional[int] = None

    def set_execution_context(
        self,
        tenant_id: int,
        user_id: int,
        session_id: int,
    ) -> None:
        """设置执行上下文。"""
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self._builder.set_execution_context(tenant_id, user_id, session_id)
        self._builder.set_group_chat_callback(self._handle_builder_message)

    def set_message_callback(self, callback: MessageCallback) -> None:
        """设置群聊消息回调。"""
        self._message_callback = callback

    def set_member_status_callback(self, callback: MemberStatusCallback) -> None:
        """设置成员状态回调。"""
        self._member_status_callback = callback

    def set_supplement_loader(self, loader: SupplementLoader) -> None:
        """设置用户补充要求加载器（从 DB/队列拉取运行中发言）。"""
        self._supplement_loader = loader

    def _now_iso(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _set_member_status(self, role: str, status: str) -> None:
        if self._member_status_callback:
            self._member_status_callback(role, status)

    def _emit_message(
        self,
        role: str,
        message_type: str,
        content: str,
        *,
        attachments: list[dict[str, Any]] | None = None,
        metadata: dict[str, Any] | None = None,
        receiver: str | None = None,
    ) -> dict[str, Any]:
        """构造并推送标准化 Agent 消息。"""
        role_info = AGENT_ROLES.get(role, AGENT_ROLES["project_manager"])
        message: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": self._now_iso(),
            "sender": {
                "id": role_info["id"],
                "name": role_info["name"],
                "role": role,
                "avatar": role_info["avatar"],
            },
            "receiver": receiver,
            "type": message_type,
            "content": content,
            "attachments": attachments or [],
            "metadata": metadata or {},
        }
        if self._message_callback:
            self._message_callback(message)
        return message

    def _handle_builder_message(self, payload: dict[str, Any]) -> None:
        """接收 WorkflowBuilder 转发的群聊消息。"""
        if self._message_callback:
            self._message_callback(payload)

    def build_graph(self):
        """构建群聊协同 LangGraph。"""
        workflow = StateGraph(GroupChatState)

        workflow.add_node("project_manager", self.project_manager_node)
        workflow.add_node("researcher", self.researcher_node)
        workflow.add_node("engineer", self.engineer_node)
        workflow.add_node("analyst", self.analyst_node)
        workflow.add_node("auditor", self.auditor_node)

        workflow.set_entry_point("project_manager")

        workflow.add_conditional_edges(
            "project_manager",
            self.route_after_pm,
            {
                "researcher": "researcher",
                "engineer": "engineer",
                "analyst": "analyst",
                "auditor": "auditor",
                "end": END,
            },
        )
        workflow.add_edge("researcher", "project_manager")
        workflow.add_edge("engineer", "project_manager")
        workflow.add_edge("analyst", "project_manager")

        workflow.add_conditional_edges(
            "auditor",
            self.route_after_auditor,
            {
                "project_manager": "project_manager",
                "end": END,
            },
        )

        checkpointer = RedisSaver(self._builder.redis)
        return workflow.compile(checkpointer=checkpointer)

    def _get_pending_subtask(self, state: GroupChatState) -> Optional[dict[str, Any]]:
        """获取下一个待执行子任务。"""
        for subtask in state.get("subtasks", []):
            if subtask.get("status") != "completed":
                return subtask
        return None

    def _mark_subtask_completed(
        self, state: GroupChatState, subtask_id: str
    ) -> None:
        """标记子任务完成。"""
        for subtask in state.get("subtasks", []):
            if subtask.get("id") == subtask_id:
                subtask["status"] = "completed"
                break

    def _calc_progress(self, state: GroupChatState) -> float:
        """计算整体进度百分比。"""
        subtasks = state.get("subtasks", [])
        if not subtasks:
            return state.get("progress", 0.0)
        completed = sum(1 for t in subtasks if t.get("status") == "completed")
        base = (completed / len(subtasks)) * 80
        if state.get("status") == "reviewing":
            return min(base + 10, 90)
        if state.get("status") == "completed":
            return 100.0
        return min(base, 80.0)

    def project_manager_node(self, state: GroupChatState) -> GroupChatState:
        """项目经理：拆解任务、分配、协调、汇总交付。"""
        state = dict(state)
        state.setdefault("results", {})
        state.setdefault("deliverables", [])
        state.setdefault("user_supplements", [])
        state.setdefault("member_statuses", {})
        state.setdefault("review_count", 0)

        self._set_member_status("project_manager", "thinking")

        # 从外部加载运行中用户补充
        if self._supplement_loader:
            loaded = self._supplement_loader()
            if loaded:
                state.setdefault("user_supplements", [])
                state["user_supplements"].extend(loaded)

        # 用户补充要求处理
        supplements = state.get("user_supplements") or []
        if supplements:
            latest = supplements[-1]
            self._emit_message(
                "project_manager",
                "task_assignment",
                f"收到用户补充要求，已转发给团队：{latest}",
            )
            state["user_supplements"] = []

        # 审核打回后重新分配
        reject_assignee = state.pop("_reject_assignee", None)
        if reject_assignee:
            self._emit_message(
                "project_manager",
                "task_assignment",
                f"审核未通过，已将修改任务分配给{AGENT_ROLES.get(reject_assignee, {}).get('name', reject_assignee)}",
                metadata={"assignee": reject_assignee},
            )
            state["status"] = "running"
            self._set_member_status("project_manager", "idle")
            return state

        # 首次进入：任务拆解
        if not state.get("subtasks"):
            self._emit_message(
                "project_manager",
                "task_start",
                f"收到任务！我来拆解并分配给团队成员：\n\n**{state['task']}**",
            )
            agent_state = self._to_agent_state(state)
            agent_state = self._builder.scheduler_node(agent_state)
            if agent_state.get("status") == "failed":
                state["status"] = "failed"
                state["error"] = agent_state.get("error", "任务拆解失败")
                self._emit_message("project_manager", "error", state["error"])
                self._set_member_status("project_manager", "idle")
                return state

            subtasks: list[dict[str, Any]] = []
            for idx, item in enumerate(agent_state.get("subtasks", [])):
                agent_type = item.get("agent", "search")
                role = SUBTASK_ROLE_MAP.get(agent_type, "analyst")
                subtasks.append(
                    {
                        "id": f"subtask_{idx + 1}",
                        "agent": agent_type,
                        "role": role,
                        "task": item.get("task", state["task"]),
                        "status": "pending",
                    }
                )
            if not subtasks:
                subtasks.append(
                    {
                        "id": "subtask_1",
                        "agent": "search",
                        "role": "researcher",
                        "task": state["task"],
                        "status": "pending",
                    }
                )

            # 确保包含分析师汇总子任务
            if not any(s.get("role") == "analyst" for s in subtasks):
                subtasks.append(
                    {
                        "id": f"subtask_{len(subtasks) + 1}",
                        "agent": "analysis",
                        "role": "analyst",
                        "task": f"基于已有资料汇总并生成分析报告：{state['task']}",
                        "status": "pending",
                    }
                )

            state["subtasks"] = subtasks
            state["status"] = "running"
            state["current_step"] = 1
            lines = [
                f"{idx + 1}. {AGENT_ROLES[s['role']]['name']}：{s['task']}"
                for idx, s in enumerate(subtasks)
            ]
            self._emit_message(
                "project_manager",
                "task_assignment",
                "任务拆解完成，分配如下：\n" + "\n".join(lines),
                metadata={"subtasks": subtasks},
            )
            state["progress"] = 10.0
            self._set_member_status("project_manager", "idle")
            return state

        # 检查是否全部完成，提交审核
        pending = self._get_pending_subtask(state)
        if pending is None:
            if state.get("status") != "reviewing" and state.get("status") != "completed":
                state["status"] = "reviewing"
                state["progress"] = 85.0
                self._emit_message(
                    "project_manager",
                    "review_request",
                    "所有子任务已完成，提交审核员进行最终审核。",
                    attachments=[
                        {
                            "type": "text",
                            "name": "交付物汇总",
                            "content": json.dumps(
                                state.get("deliverables", []),
                                ensure_ascii=False,
                                indent=2,
                            ),
                        }
                    ],
                )
            self._set_member_status("project_manager", "idle")
            return state

        # 分配下一个子任务
        role = pending.get("role", "researcher")
        self._emit_message(
            "project_manager",
            "task_assignment",
            f"分配任务给{AGENT_ROLES[role]['name']}：{pending.get('task', '')}",
            metadata={"task_id": pending.get("id"), "assignee": role},
            receiver=role,
        )
        state["current_subtask_index"] = state.get("subtasks", []).index(pending)
        state["progress"] = self._calc_progress(state)
        self._set_member_status("project_manager", "idle")
        return state

    def route_after_pm(self, state: GroupChatState) -> str:
        """项目经理节点后的路由。"""
        if state.get("status") == "failed":
            return "end"
        if state.get("status") == "completed":
            return "end"
        if state.get("status") == "human_review":
            return "end"
        if state.get("_reject_assignee"):
            role = state["_reject_assignee"]
            if role in ("researcher", "engineer", "analyst"):
                return role
            return "researcher"
        if state.get("status") == "reviewing":
            return "auditor"

        pending = self._get_pending_subtask(state)
        if not pending:
            return "auditor"
        role = pending.get("role", "researcher")
        if role in ("researcher", "engineer", "analyst"):
            return role
        return "researcher"

    def _execute_subtask(
        self,
        state: GroupChatState,
        role: str,
        node_method: Callable[[Any], Any],
        result_key: str,
    ) -> GroupChatState:
        """执行当前子任务并发送群聊消息。"""
        state = dict(state)
        pending = self._get_pending_subtask(state)
        if not pending or pending.get("role") != role:
            return state

        task_desc = pending.get("task", state["task"])
        subtask_id = pending.get("id", "")
        self._set_member_status(role, "working")
        started = time.monotonic()

        self._emit_message(
            role,
            "progress_update",
            f"收到，开始处理：{task_desc}",
            metadata={"task_id": subtask_id, "step": state.get("current_step", 0)},
        )

        agent_state = self._to_agent_state(state)
        try:
            agent_state = node_method(agent_state)
            result = str((agent_state.get("results") or {}).get(result_key, ""))
            tool_calls = agent_state.get("tool_calls") or []
            duration_ms = int((time.monotonic() - started) * 1000)

            attachments: list[dict[str, Any]] = []
            if result_key == "execution" and result:
                attachments.append(
                    {"type": "code", "name": "执行结果", "content": result, "language": "python"}
                )
            elif result_key in ("knowledge", "search") and result:
                attachments.append({"type": "text", "name": "检索结果", "content": result})
            elif result_key == "analysis" and result:
                attachments.append({"type": "table", "name": "分析结果", "content": result})

            thought = f"调用 {result_key} Agent 完成任务，耗时 {duration_ms}ms"
            self._emit_message(
                role,
                "result_delivery",
                f"任务完成！{task_desc[:50]}...",
                attachments=attachments,
                metadata={
                    "task_id": subtask_id,
                    "duration": duration_ms,
                    "tool_calls": tool_calls,
                    "thought": thought,
                },
            )

            state.setdefault("results", {})[result_key] = result
            deliverable = {
                "role": role,
                "task_id": subtask_id,
                "content": result,
                "attachments": attachments,
            }
            state.setdefault("deliverables", []).append(deliverable)
            self._mark_subtask_completed(state, subtask_id)
            state["progress"] = self._calc_progress(state)

            self._emit_message(
                role,
                "answer",
                f"【{AGENT_ROLES[role]['name']}】任务「{task_desc[:30]}」已完成，请查收。",
                receiver="project_manager",
            )
        except Exception as exc:
            logger.exception("群聊子任务执行失败 role=%s: %s", role, exc)
            state.setdefault("results", {})[result_key] = f"执行失败: {exc}"
            self._emit_message(role, "error", f"任务执行失败：{exc}")
            self._mark_subtask_completed(state, subtask_id)

        self._set_member_status(role, "idle")
        return state

    def researcher_node(self, state: GroupChatState) -> GroupChatState:
        """研究员：知识库检索与联网搜索。"""
        pending = self._get_pending_subtask(state)
        if not pending:
            return state
        agent_type = pending.get("agent", "search")
        if agent_type == "knowledge":
            return self._execute_subtask(
                state, "researcher", self._builder.knowledge_agent_node, "knowledge"
            )
        return self._execute_subtask(
            state, "researcher", self._builder.search_agent_node, "search"
        )

    def engineer_node(self, state: GroupChatState) -> GroupChatState:
        """工程师：代码编写与工具调用。"""
        return self._execute_subtask(
            state, "engineer", self._builder.execution_agent_node, "execution"
        )

    def analyst_node(self, state: GroupChatState) -> GroupChatState:
        """分析师：数据处理与报告撰写。"""
        state = dict(state)
        pending = self._get_pending_subtask(state)
        if not pending:
            return state

        self._set_member_status("analyst", "working")
        task_desc = pending.get("task", state["task"])
        subtask_id = pending.get("id", "")
        started = time.monotonic()

        self._emit_message(
            "analyst",
            "progress_update",
            f"收到，开始分析：{task_desc}",
            metadata={"task_id": subtask_id},
        )

        results = state.get("results", {})
        llm = self._builder._create_llm()
        analysis_prompt = f"""
请基于以下资料完成数据分析与报告撰写：

原始任务：{state['task']}
分析要求：{task_desc}

已有资料：
{json.dumps(results, ensure_ascii=False, default=str)}

请输出结构化的分析报告，包含关键发现、数据摘要和建议。
"""
        analysis_result = ""
        thought = "基于已有检索与工程结果进行综合分析"
        try:
            if llm is not None:
                response = llm.invoke(analysis_prompt)
                content = response.content
                analysis_result = content if isinstance(content, str) else str(content)
            else:
                analysis_result = (
                    f"【分析报告】\n\n任务：{task_desc}\n\n"
                    f"数据摘要：\n{json.dumps(results, ensure_ascii=False, indent=2)}"
                )
        except Exception as exc:
            logger.exception("分析师节点失败: %s", exc)
            analysis_result = f"分析失败: {exc}"

        duration_ms = int((time.monotonic() - started) * 1000)
        attachments = [
            {"type": "chart", "name": "分析图表", "content": {"type": "bar", "summary": analysis_result[:200]}},
            {"type": "text", "name": "分析报告", "content": analysis_result},
        ]
        self._emit_message(
            "analyst",
            "result_delivery",
            "分析报告已完成，请查收。",
            attachments=attachments,
            metadata={
                "task_id": subtask_id,
                "duration": duration_ms,
                "thought": thought,
            },
        )

        state.setdefault("results", {})["analysis"] = analysis_result
        state.setdefault("deliverables", []).append(
            {"role": "analyst", "task_id": subtask_id, "content": analysis_result, "attachments": attachments}
        )
        self._mark_subtask_completed(state, subtask_id)
        state["progress"] = self._calc_progress(state)
        self._set_member_status("analyst", "idle")
        return state

    def auditor_node(self, state: GroupChatState) -> GroupChatState:
        """审核员：四维度审核，最多打回三次。"""
        state = dict(state)
        review_count = int(state.get("review_count") or 0)
        self._set_member_status("auditor", "working")

        self._emit_message(
            "auditor",
            "progress_update",
            "开始审核最终成果，将从完整性、数据准确性、逻辑合理性、合规性四个维度评估...",
        )

        deliverables = state.get("deliverables", [])
        results = state.get("results", {})
        llm = self._builder._create_llm()

        review_prompt = f"""
你是严格的成果审核员，请从以下四个维度审核交付物：
1. 内容完整性：是否覆盖任务要求的全部要点
2. 数据准确性：数据来源是否可靠，计算是否正确
3. 逻辑合理性：分析过程是否符合逻辑
4. 合规性：是否包含敏感或违规内容

原始任务：{state['task']}

交付物：
{json.dumps(deliverables, ensure_ascii=False, default=str)}

子任务结果：
{json.dumps(results, ensure_ascii=False, default=str)}

请仅输出 JSON：
{{
  "passed": true/false,
  "grade": "pass" | "conditional" | "reject",
  "issues": ["问题1", "问题2"],
  "assignee": "researcher" | "engineer" | "analyst",
  "summary": "审核意见摘要"
}}
"""
        review_result: dict[str, Any] = {
            "passed": True,
            "grade": "pass",
            "issues": [],
            "assignee": "analyst",
            "summary": "成果符合基本要求",
            "dimensions": {
                "completeness": True,
                "accuracy": True,
                "logic": True,
                "compliance": True,
            },
        }

        try:
            if llm is not None:
                response = llm.invoke(review_prompt)
                content = response.content if isinstance(response.content, str) else str(response.content)
                text = content.strip()
                if text.startswith("```"):
                    text = text.split("```")[1]
                    if text.startswith("json"):
                        text = text[4:]
                start = text.find("{")
                end = text.rfind("}")
                if start >= 0 and end > start:
                    parsed = json.loads(text[start : end + 1])
                    review_result.update(parsed)
        except Exception as exc:
            logger.warning("审核 LLM 解析失败，默认通过: %s", exc)

        state["review_result"] = review_result
        passed = bool(review_result.get("passed"))

        if passed:
            final_answer = self._build_final_answer(state)
            state["final_answer"] = final_answer
            state["status"] = "completed"
            state["progress"] = 100.0
            self._emit_message(
                "auditor",
                "review_result",
                f"✅ 审核通过！{review_result.get('summary', '')}",
                metadata={"review": review_result, "grade": review_result.get("grade")},
            )
            self._emit_message(
                "project_manager",
                "task_complete",
                "🎉 所有审核通过，任务完成！最终交付物如下：",
                attachments=[
                    {"type": "text", "name": "最终报告", "content": final_answer},
                ],
            )
            self._set_member_status("auditor", "idle")
            return state

        review_count += 1
        state["review_count"] = review_count
        issues = review_result.get("issues") or ["成果未达标准"]
        issue_text = "\n".join(f"{idx + 1}. {item}" for idx, item in enumerate(issues))

        if review_count >= MAX_REVIEW_RETRIES:
            state["status"] = "human_review"
            state["error"] = "审核员连续3次审核不通过，已转人工审核"
            self._emit_message(
                "auditor",
                "review_result",
                f"❌ 第{review_count}次审核不通过，已达最大打回次数。\n{issue_text}\n\n已提交人工审核。",
                metadata={"review": review_result, "human_review": True},
            )
            self._set_member_status("auditor", "idle")
            return state

        assignee = review_result.get("assignee", "analyst")
        if assignee not in AGENT_ROLES:
            assignee = "analyst"

        # 重置对应子任务状态以便重新执行
        for subtask in state.get("subtasks", []):
            if subtask.get("role") == assignee:
                subtask["status"] = "pending"
                subtask["task"] = f"【修改】{'; '.join(issues[:2])} — {subtask.get('task', '')}"
                break

        state["status"] = "running"
        state["_reject_assignee"] = assignee
        self._emit_message(
            "auditor",
            "review_result",
            f"❌ 审核不通过（第{review_count}次），请修改后重新提交：\n{issue_text}",
            metadata={"review": review_result, "assignee": assignee, "retry": review_count},
        )
        self._set_member_status("auditor", "idle")
        return state

    def route_after_auditor(self, state: GroupChatState) -> str:
        """审核后路由。"""
        if state.get("status") == "completed":
            return "end"
        if state.get("status") == "human_review":
            return "end"
        if state.get("status") == "failed":
            return "end"
        return "project_manager"

    def _build_final_answer(self, state: GroupChatState) -> str:
        """汇总最终交付物。"""
        parts = [f"# 任务交付报告\n\n**任务**：{state['task']}\n"]
        for item in state.get("deliverables", []):
            role_name = AGENT_ROLES.get(item.get("role", ""), {}).get("name", "成员")
            parts.append(f"\n## {role_name}交付\n\n{item.get('content', '')}")
        review = state.get("review_result") or {}
        parts.append(f"\n\n---\n**审核结论**：{review.get('summary', '通过')}")
        return "\n".join(parts)

    def _to_agent_state(self, state: GroupChatState) -> dict[str, Any]:
        """群聊状态转 WorkflowBuilder AgentState。"""
        return {
            "messages": [],
            "task": state.get("task", ""),
            "subtasks": [
                {"agent": s.get("agent"), "task": s.get("task")}
                for s in state.get("subtasks", [])
            ]
            or [],
            "results": dict(state.get("results") or {}),
            "current_step": "group_chat",
            "status": "running",
            "error": "",
            "require_human_approval": False,
            "human_approved": False,
            "kb_id": state.get("kb_id"),
            "execution_logs": [],
            "loop_counters": {},
            "replan_count": 0,
            "node_configs": state.get("node_configs") or {},
            "tool_calls": [],
            "tenant_id": self.tenant_id,
            "user_id": self.user_id,
        }

    @staticmethod
    def get_members(statuses: dict[str, str] | None = None) -> list[dict[str, Any]]:
        """返回标准成员列表及状态。"""
        statuses = statuses or {}
        return [
            {
                "role": role,
                "name": info["name"],
                "avatar": info["avatar"],
                "color": info["color"],
                "status": statuses.get(role, "idle"),
            }
            for role, info in AGENT_ROLES.items()
        ]

    @staticmethod
    def get_progress_steps(session_status: str, subtasks: list[dict[str, Any]]) -> list[dict[str, str]]:
        """根据会话状态生成进度步骤。"""
        has_research = any(s.get("role") == "researcher" for s in subtasks)
        has_engineer = any(s.get("role") == "engineer" for s in subtasks)
        has_analyst = any(s.get("role") == "analyst" for s in subtasks)

        def subtask_status(role: str) -> str:
            role_tasks = [s for s in subtasks if s.get("role") == role]
            if not role_tasks:
                return "skipped"
            if all(s.get("status") == "completed" for s in role_tasks):
                return "completed"
            if any(s.get("status") == "completed" for s in role_tasks):
                return "running"
            return "pending"

        steps: list[dict[str, str]] = [
            {
                "key": "decompose",
                "label": "任务拆解",
                "status": "completed" if subtasks else "pending",
            },
        ]
        if has_research:
            steps.append({"key": "research", "label": "资料检索", "status": subtask_status("researcher")})
        if has_engineer:
            steps.append({"key": "engineering", "label": "工程实现", "status": subtask_status("engineer")})
        if has_analyst:
            steps.append({"key": "analysis", "label": "数据分析", "status": subtask_status("analyst")})

        review_status = "pending"
        if session_status == "reviewing":
            review_status = "running"
        elif session_status in ("completed", "human_review"):
            review_status = "completed"
        steps.append({"key": "review", "label": "成果审核", "status": review_status})

        delivery_status = "completed" if session_status == "completed" else "pending"
        steps.append({"key": "delivery", "label": "最终交付", "status": delivery_status})
        return steps
