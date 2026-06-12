"""
插件与 Skill 数据模型。
"""

from datetime import datetime
from typing import TYPE_CHECKING, Any, List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.mixins import TimestampMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.user import User


class Plugin(Base, TimestampMixin):
    """插件市场目录表。"""

    __tablename__ = "plugins"
    __table_args__ = (
        UniqueConstraint("plugin_id", name="uq_plugins_plugin_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plugin_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    author: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    icon: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    manifest: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_official: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_featured: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    download_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    rating_avg: Mapped[float] = mapped_column(Float, nullable=False, server_default="0")
    rating_count: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    signature: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="published")

    skills: Mapped[List["Skill"]] = relationship(back_populates="plugin")
    installations: Mapped[List["PluginInstallation"]] = relationship(back_populates="plugin")
    reviews: Mapped[List["PluginReview"]] = relationship(back_populates="plugin")


class PluginInstallation(Base, TimestampMixin):
    """租户插件安装记录。"""

    __tablename__ = "plugin_installations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "plugin_id", name="uq_plugin_installations_tenant_plugin"),
        CheckConstraint(
            "status IN ('installed', 'enabled', 'disabled', 'uninstalled')",
            name="ck_plugin_installations_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    plugin_id: Mapped[int] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    installed_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False, server_default="installed")
    installed_version: Mapped[str] = mapped_column(String(20), nullable=False)
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    installed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plugin: Mapped["Plugin"] = relationship(back_populates="installations")
    tenant: Mapped["Tenant"] = relationship(back_populates="plugin_installations")
    installed_by_user: Mapped[Optional["User"]] = relationship()


class Skill(Base, TimestampMixin):
    """Skill 定义表。"""

    __tablename__ = "skills"
    __table_args__ = (
        UniqueConstraint("tenant_id", "skill_key", name="uq_skills_tenant_skill_key"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    plugin_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("plugins.id", ondelete="SET NULL"), nullable=True
    )
    mcp_server_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("mcp_servers.id", ondelete="SET NULL"), nullable=True
    )
    mcp_tool_name: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    handler: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    permissions: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")
    config_schema: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    version: Mapped[str] = mapped_column(String(20), nullable=False, server_default="1.0.0")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    is_native: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    icon: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, server_default="[]")

    plugin: Mapped[Optional["Plugin"]] = relationship(back_populates="skills")
    configs: Mapped[List["SkillConfig"]] = relationship(back_populates="skill")


class SkillConfig(Base, TimestampMixin):
    """租户 Skill 配置。"""

    __tablename__ = "skill_configs"
    __table_args__ = (
        UniqueConstraint("tenant_id", "skill_id", name="uq_skill_configs_tenant_skill"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    skill_id: Mapped[int] = mapped_column(
        ForeignKey("skills.id", ondelete="CASCADE"), nullable=False, index=True
    )
    config: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")

    skill: Mapped["Skill"] = relationship(back_populates="configs")


class PluginReview(Base):
    """插件评分与评论。"""

    __tablename__ = "plugin_reviews"
    __table_args__ = (
        UniqueConstraint("plugin_id", "user_id", name="uq_plugin_reviews_plugin_user"),
        CheckConstraint("rating >= 1 AND rating <= 5", name="ck_plugin_reviews_rating"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    plugin_id: Mapped[int] = mapped_column(
        ForeignKey("plugins.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    plugin: Mapped["Plugin"] = relationship(back_populates="reviews")


class SkillExecutionLog(Base):
    """Skill 执行审计日志。"""

    __tablename__ = "skill_execution_logs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    tenant_id: Mapped[int] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    skill_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("skills.id", ondelete="SET NULL"), nullable=True, index=True
    )
    skill_key: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    parameters: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    result_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sandbox_level: Mapped[str] = mapped_column(String(20), nullable=False, server_default="basic")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )
