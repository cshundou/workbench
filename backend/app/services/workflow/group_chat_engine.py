"""
群聊式多 Agent 协同引擎（统一架构）。

群聊模式复用 WorkflowBuilder 标准工作流图，支持动态智能团队配置。
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from app.core.config import settings
from app.services.user_key_context import UserKeyContext
from app.services.workflow.graph_builder import WorkflowBuilder
from app.services.workflow.nodes.constants import (
    AGENT_ROLES,
    MAX_REVIEW_RETRIES,
)
from app.services.workflow.role_catalog import build_role_lookup

logger = logging.getLogger(__name__)

MessageCallback = Callable[[dict[str, Any]], None]
MemberStatusCallback = Callable[[str, str], None]
SupplementLoader = Callable[[], list[str]]


class GroupChatEngine:
    """群聊式多 Agent 协同引擎（委托统一 WorkflowBuilder 执行）。"""

    def __init__(
        self,
        redis_url: str | None = None,
        user_ctx: UserKeyContext | None = None,
        team_config: dict[str, Any] | None = None,
    ) -> None:
        self._builder = WorkflowBuilder(redis_url=redis_url, user_ctx=user_ctx)
        self._team_config = team_config or {}
        self._message_callback: Optional[MessageCallback] = None
        self.session_id: Optional[int] = None
        self.tenant_id: Optional[int] = None
        self.user_id: Optional[int] = None
        self._member_meta: dict[str, dict[str, Any]] = {}

    def set_team_config(self, team_config: dict[str, Any]) -> None:
        """设置动态团队配置。"""
        self._team_config = team_config
        self._builder.set_team_config(team_config)

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

    def set_message_callback(self, callback: MessageCallback) -> None:
        """设置群聊消息回调。"""
        self._message_callback = callback
        self._builder.set_group_chat_callback(callback)

    def set_member_status_callback(self, callback: MemberStatusCallback) -> None:
        """设置成员状态回调。"""
        self._builder.set_member_status_callback(callback)

    def set_supplement_loader(self, loader: SupplementLoader) -> None:
        """设置用户补充要求加载器。"""
        self._builder.set_supplement_loader(loader)

    def build_graph(self):
        """构建群聊协同 LangGraph（支持动态团队）。"""
        return self._builder.build_dynamic_group_chat_workflow(self._team_config)

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
        """向后兼容：构造并推送标准化 Agent 消息。"""
        import uuid
        from datetime import datetime, timezone

        lookup = build_role_lookup(self._team_config.get("members"))
        role_info = lookup.get(role, AGENT_ROLES.get(role, AGENT_ROLES["project_manager"]))
        message: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
        if self._message_callback:
            self._message_callback(message)
        return message

    @staticmethod
    def get_members(
        statuses: dict[str, str] | None = None,
        team_config: dict[str, Any] | None = None,
        subtasks: list[dict[str, Any]] | None = None,
        session_status: str = "pending",
        review_count: int = 0,
        reject_info: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """
        返回动态团队成员列表及状态。

        支持 5 种状态：pending / thinking / working / completed / error
        审核环节附加 review_round、reject_reason。
        """
        statuses = statuses or {}
        reject_info = reject_info or {}
        members_cfg = (team_config or {}).get("members", [])

        if not members_cfg:
            # 向后兼容：经典五角色
            return [
                GroupChatEngine._build_member_item(
                    role_id=role,
                    info=info,
                    status=statuses.get(role, "pending"),
                    subtasks=subtasks,
                    session_status=session_status,
                    review_count=review_count,
                    reject_info=reject_info,
                )
                for role, info in AGENT_ROLES.items()
            ]

        result: list[dict[str, Any]] = []
        for member in members_cfg:
            role_id = member.get("role_id") or member.get("role", "")
            lookup = build_role_lookup(members_cfg)
            info = lookup.get(role_id, {})
            status = statuses.get(role_id, "pending")
            result.append(
                GroupChatEngine._build_member_item(
                    role_id=role_id,
                    info={
                        "name": member.get("name", info.get("name", role_id)),
                        "avatar": member.get("avatar", info.get("avatar", "🤖")),
                        "color": member.get("color", info.get("color", "#1677FF")),
                    },
                    status=status,
                    subtasks=subtasks,
                    session_status=session_status,
                    review_count=review_count,
                    reject_info=reject_info,
                    member_subtasks=member.get("subtasks", []),
                )
            )
        return result

    @staticmethod
    def _build_member_item(
        role_id: str,
        info: dict[str, Any],
        status: str,
        subtasks: list[dict[str, Any]] | None,
        session_status: str,
        review_count: int,
        reject_info: dict[str, Any],
        member_subtasks: list[str] | None = None,
    ) -> dict[str, Any]:
        """构建单个成员状态项。"""
        role_tasks = [s for s in (subtasks or []) if s.get("role") == role_id]
        total = len(member_subtasks) if member_subtasks else max(len(role_tasks), 1)
        completed = sum(1 for t in role_tasks if t.get("status") == "completed")

        current_task: str | None = None
        for t in role_tasks:
            if t.get("status") != "completed":
                current_task = t.get("task")
                break
        if current_task is None and member_subtasks and completed < total:
            current_task = member_subtasks[completed] if completed < len(member_subtasks) else None

        is_auditor = role_id in ("auditor", "compliance_officer")
        item: dict[str, Any] = {
            "role": role_id,
            "name": info.get("name", role_id),
            "avatar": info.get("avatar", "🤖"),
            "color": info.get("color", "#1677FF"),
            "status": status,
            "current_task": current_task,
            "completed_count": completed,
            "total_count": total,
            "is_auditor": is_auditor,
        }
        if is_auditor and session_status == "reviewing":
            item["review_round"] = review_count + 1
        if reject_info.get("assignee") == role_id:
            item["status"] = "revision"
            item["reject_reason"] = reject_info.get("reason")
        if session_status == "human_review" and is_auditor:
            item["status"] = "error"
        return item

    @staticmethod
    def get_progress_steps(
        session_status: str,
        subtasks: list[dict[str, Any]],
        team_config: dict[str, Any] | None = None,
    ) -> list[dict[str, str]]:
        """根据会话状态与团队配置生成动态进度步骤。"""
        members = (team_config or {}).get("members", [])
        workflow_phases = (team_config or {}).get("workflow_phases") or []
        if workflow_phases:
            steps: list[dict[str, str]] = []
            for phase in workflow_phases:
                phase_num = int(phase.get("phase", 0))
                if phase_num == 0:
                    steps.append(
                        {
                            "key": "team_build",
                            "label": phase.get("label", "智能组队"),
                            "status": "completed",
                        }
                    )
                    continue
                if phase_num >= 100:
                    review_status = "pending"
                    if session_status == "reviewing":
                        review_status = "running"
                    elif session_status in ("completed", "human_review"):
                        review_status = "completed"
                    steps.append(
                        {
                            "key": "audit",
                            "label": phase.get("label", "终审交付"),
                            "status": review_status,
                        }
                    )
                    continue
                phase_subtasks = [
                    s for s in subtasks if int(s.get("phase") or 2) == phase_num
                ]
                if not phase_subtasks:
                    step_status = "pending"
                elif all(t.get("status") == "completed" for t in phase_subtasks):
                    step_status = "completed"
                elif any(t.get("status") == "completed" for t in phase_subtasks):
                    step_status = "running"
                else:
                    step_status = "pending"
                steps.append(
                    {
                        "key": f"phase_{phase_num}",
                        "label": phase.get("label", f"阶段{phase_num}"),
                        "status": step_status,
                    }
                )
            delivery_status = "completed" if session_status == "completed" else "pending"
            steps.append({"key": "delivery", "label": "最终交付", "status": delivery_status})
            return steps

        if members:
            steps = [
                {
                    "key": "team_build",
                    "label": "智能组队",
                    "status": "completed",
                },
                {
                    "key": "decompose",
                    "label": "任务拆解",
                    "status": "completed" if subtasks else "pending",
                },
            ]
            for member in members:
                role_id = member.get("role_id", "")
                if role_id in ("auditor", "project_manager"):
                    continue
                role_tasks = [s for s in subtasks if s.get("role") == role_id]
                if not role_tasks:
                    step_status = "skipped"
                elif all(t.get("status") == "completed" for t in role_tasks):
                    step_status = "completed"
                elif any(t.get("status") == "completed" for t in role_tasks):
                    step_status = "running"
                else:
                    step_status = "pending"
                steps.append(
                    {
                        "key": role_id,
                        "label": member.get("name", role_id),
                        "status": step_status,
                    }
                )
            review_status = "pending"
            if session_status == "reviewing":
                review_status = "running"
            elif session_status in ("completed", "human_review"):
                review_status = "completed"
            steps.append({"key": "review", "label": "成果审核", "status": review_status})
            delivery_status = "completed" if session_status == "completed" else "pending"
            steps.append({"key": "delivery", "label": "最终交付", "status": delivery_status})
            return steps

        # 经典五角色进度
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

        steps = [
            {
                "key": "decompose",
                "label": "任务拆解",
                "status": "completed" if subtasks else "pending",
            },
        ]
        if has_research:
            steps.append(
                {"key": "research", "label": "资料检索", "status": subtask_status("researcher")}
            )
        if has_engineer:
            steps.append(
                {"key": "engineering", "label": "工程实现", "status": subtask_status("engineer")}
            )
        if has_analyst:
            steps.append(
                {"key": "analysis", "label": "数据分析", "status": subtask_status("analyst")}
            )
        review_status = "pending"
        if session_status == "reviewing":
            review_status = "running"
        elif session_status in ("completed", "human_review"):
            review_status = "completed"
        steps.append({"key": "review", "label": "成果审核", "status": review_status})
        delivery_status = "completed" if session_status == "completed" else "pending"
        steps.append({"key": "delivery", "label": "最终交付", "status": delivery_status})
        return steps
