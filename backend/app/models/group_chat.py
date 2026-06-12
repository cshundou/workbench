"""
群聊式多 Agent 协同会话与消息模型。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User
    from app.models.workflow import Workflow
    from app.models.workflow_execution import WorkflowExecution


class GroupChatSession(Base, TimestampMixin):
    """群聊协同会话表。"""

    __tablename__ = "group_chat_sessions"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'running', 'reviewing', 'completed', 'failed', 'human_review', 'cancelled')",
            name="ck_group_chat_sessions_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    workflow_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflows.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    execution_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("workflow_executions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    task_description: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    progress: Mapped[float] = mapped_column(nullable=False, server_default="0")
    current_step: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    subtasks: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    deliverables: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    review_result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSONB, nullable=True)
    review_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    kb_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    extra_params: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="group_chat_sessions")
    user: Mapped["User"] = relationship(back_populates="group_chat_sessions")
    workflow: Mapped[Optional["Workflow"]] = relationship(back_populates="group_chat_sessions")
    execution: Mapped[Optional["WorkflowExecution"]] = relationship(
        back_populates="group_chat_session"
    )
    messages: Mapped[list["GroupChatMessage"]] = relationship(
        back_populates="session",
        cascade="all, delete-orphan",
        order_by="GroupChatMessage.id",
    )


class GroupChatMessage(Base):
    """群聊消息表（标准化 Agent 消息协议）。"""

    __tablename__ = "group_chat_messages"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("group_chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    message_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    sender_role: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    message_type: Mapped[str] = mapped_column(String(30), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    session: Mapped["GroupChatSession"] = relationship(back_populates="messages")
