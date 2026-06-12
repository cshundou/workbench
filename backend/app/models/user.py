"""
用户模型。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.agent import Agent
    from app.models.chat_history import ChatHistory
    from app.models.document import Document
    from app.models.knowledge_base import KnowledgeBase
    from app.models.role import Role
    from app.models.tenant import Tenant
    from app.models.token_usage import TokenUsage
    from app.models.workflow import Workflow
    from app.models.user_api_key import UserApiKey
    from app.models.group_chat import GroupChatSession
    from app.models.professional_role import ProfessionalRole, TeamTemplate


class User(Base, TimestampMixin):
    """用户表。"""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("status IN (0, 1)", name="ck_users_status"),
        UniqueConstraint("tenant_id", "username", name="uq_users_tenant_id_username"),
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(String(100), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("roles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[int] = mapped_column(SmallInteger, default=1, nullable=False)
    last_login_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    last_login_ip: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="users")
    role: Mapped[Optional["Role"]] = relationship(back_populates="users")
    owned_knowledge_bases: Mapped[list["KnowledgeBase"]] = relationship(
        back_populates="owner"
    )
    uploaded_documents: Mapped[list["Document"]] = relationship(
        back_populates="uploader"
    )
    owned_agents: Mapped[list["Agent"]] = relationship(back_populates="owner")
    owned_workflows: Mapped[list["Workflow"]] = relationship(back_populates="owner")
    workflow_executions: Mapped[list["WorkflowExecution"]] = relationship(
        back_populates="created_by_user"
    )
    group_chat_sessions: Mapped[list["GroupChatSession"]] = relationship(
        back_populates="user"
    )
    chat_histories: Mapped[list["ChatHistory"]] = relationship(back_populates="user")
    token_usages: Mapped[list["TokenUsage"]] = relationship(back_populates="user")
    api_keys: Mapped[list["UserApiKey"]] = relationship(back_populates="user")
    created_professional_roles: Mapped[list["ProfessionalRole"]] = relationship(
        back_populates="creator"
    )
    team_templates: Mapped[list["TeamTemplate"]] = relationship(back_populates="owner")
