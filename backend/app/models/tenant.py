"""
租户模型。
"""

from typing import TYPE_CHECKING, List

from sqlalchemy import CheckConstraint, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.chat_history import ChatHistory
    from app.models.knowledge_base import KnowledgeBase
    from app.models.role import Role
    from app.models.token_usage import TokenUsage
    from app.models.user import User
    from app.models.workflow import Workflow
    from app.models.workflow_execution import WorkflowExecution
    from app.models.group_chat import GroupChatSession


class Tenant(Base, TimestampMixin):
    """租户表。"""

    __tablename__ = "tenants"
    __table_args__ = (
        CheckConstraint("status IN (0, 1)", name="ck_tenants_status"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    domain: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    monthly_token_limit: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    roles: Mapped[List["Role"]] = relationship(back_populates="tenant")
    users: Mapped[List["User"]] = relationship(back_populates="tenant")
    knowledge_bases: Mapped[List["KnowledgeBase"]] = relationship(back_populates="tenant")
    agents: Mapped[List["Agent"]] = relationship(back_populates="tenant")
    workflows: Mapped[List["Workflow"]] = relationship(back_populates="tenant")
    workflow_executions: Mapped[List["WorkflowExecution"]] = relationship(
        back_populates="tenant"
    )
    group_chat_sessions: Mapped[List["GroupChatSession"]] = relationship(
        back_populates="tenant"
    )
    chat_histories: Mapped[List["ChatHistory"]] = relationship(back_populates="tenant")
    token_usages: Mapped[List["TokenUsage"]] = relationship(back_populates="tenant")
