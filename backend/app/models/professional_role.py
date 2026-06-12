"""
专业角色模板数据模型（动态智能团队角色库）。
"""

from typing import TYPE_CHECKING, Any, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class ProfessionalRole(Base, TimestampMixin):
    """专业角色模板表（系统预设 + 用户自定义）。"""

    __tablename__ = "professional_roles"
    __table_args__ = (
        UniqueConstraint("tenant_id", "role_id", name="uq_professional_roles_tenant_role_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    role_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    avatar: Mapped[str] = mapped_column(String(20), nullable=False, server_default="🤖")
    category: Mapped[str] = mapped_column(String(50), nullable=False, server_default="general")
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    tools: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="[]",
    )
    responsibility: Mapped[str] = mapped_column(Text, nullable=False)
    color: Mapped[str] = mapped_column(String(20), nullable=False, server_default="#1677FF")
    is_preset: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    created_by: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    tenant: Mapped[Optional["Tenant"]] = relationship(back_populates="professional_roles")
    creator: Mapped[Optional["User"]] = relationship(back_populates="created_professional_roles")


class TeamTemplate(Base, TimestampMixin):
    """团队模板表（官方场景模板 + 用户自定义模板）。"""

    __tablename__ = "team_templates"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    scenario: Mapped[str] = mapped_column(String(50), nullable=False, server_default="general")
    team_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        server_default="{}",
    )
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")

    tenant: Mapped[Optional["Tenant"]] = relationship(back_populates="team_templates")
    owner: Mapped[Optional["User"]] = relationship(back_populates="team_templates")
