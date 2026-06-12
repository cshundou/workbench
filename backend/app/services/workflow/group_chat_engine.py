"""
群聊式多 Agent 协同引擎（统一架构）。

群聊模式复用 WorkflowBuilder 标准工作流图，通过群聊视图回调展示执行过程。
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
    PROGRESS_STEPS,
    SUBTASK_ROLE_MAP,
)
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
    ) -> None:
        self._builder = WorkflowBuilder(redis_url=redis_url, user_ctx=user_ctx)
        self._message_callback: Optional[MessageCallback] = None
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
        """构建群聊协同 LangGraph（复用统一工作流底层）。"""
        return self._builder.build_group_chat_workflow()

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

        role_info = AGENT_ROLES.get(role, AGENT_ROLES["project_manager"])
        message: dict[str, Any] = {
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
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
    def get_progress_steps(
        session_status: str, subtasks: list[dict[str, Any]]
    ) -> list[dict[str, str]]:
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
            steps.append(
                {"key": "research", "label": "资料检索", "status": subtask_status("researcher")}
            )
        if has_engineer:
            steps.append(
                {
                    "key": "engineering",
                    "label": "工程实现",
                    "status": subtask_status("engineer"),
                }
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
