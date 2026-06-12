"""插件与 Skill 系统表

Revision ID: 014
Revises: 013
Create Date: 2026-06-13
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "014"
down_revision: Union[str, None] = "013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建插件市场、Skill 与审计相关表。"""
    op.create_table(
        "plugins",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plugin_id", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("author", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("icon", sa.String(length=500), nullable=True),
        sa.Column("category", sa.String(length=50), nullable=False),
        sa.Column("tags", JSONB, server_default="[]", nullable=False),
        sa.Column("permissions", JSONB, server_default="[]", nullable=False),
        sa.Column("manifest", JSONB, server_default="{}", nullable=False),
        sa.Column("is_official", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_featured", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("download_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("rating_avg", sa.Float(), server_default="0", nullable=False),
        sa.Column("rating_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("signature", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="published", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id"),
    )
    op.create_index("ix_plugins_category", "plugins", ["category"])
    op.create_index("ix_plugins_plugin_id", "plugins", ["plugin_id"])

    op.create_table(
        "plugin_installations",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("plugin_id", sa.Integer(), nullable=False),
        sa.Column("installed_by", sa.Integer(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="installed", nullable=False),
        sa.Column("installed_version", sa.String(length=20), nullable=False),
        sa.Column("config", JSONB, server_default="{}", nullable=False),
        sa.Column("installed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint(
            "status IN ('installed', 'enabled', 'disabled', 'uninstalled')",
            name="ck_plugin_installations_status",
        ),
        sa.ForeignKeyConstraint(["installed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "plugin_id"),
    )
    op.create_index("ix_plugin_installations_tenant_id", "plugin_installations", ["tenant_id"])

    op.create_table(
        "skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("skill_key", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("plugin_id", sa.Integer(), nullable=True),
        sa.Column("mcp_server_id", sa.Integer(), nullable=True),
        sa.Column("mcp_tool_name", sa.String(length=100), nullable=True),
        sa.Column("handler", sa.Text(), nullable=True),
        sa.Column("parameters", JSONB, server_default="{}", nullable=False),
        sa.Column("permissions", JSONB, server_default="[]", nullable=False),
        sa.Column("config_schema", JSONB, server_default="{}", nullable=False),
        sa.Column("version", sa.String(length=20), server_default="1.0.0", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("is_native", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("icon", sa.String(length=200), nullable=True),
        sa.Column("tags", JSONB, server_default="[]", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["mcp_server_id"], ["mcp_servers.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "skill_key"),
    )
    op.create_index("ix_skills_skill_key", "skills", ["skill_key"])
    op.create_index("ix_skills_source_type", "skills", ["source_type"])

    op.create_table(
        "skill_configs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("skill_id", sa.Integer(), nullable=False),
        sa.Column("config", JSONB, server_default="{}", nullable=False),
        sa.Column("is_enabled", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "skill_id"),
    )

    op.create_table(
        "plugin_reviews",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("plugin_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("rating >= 1 AND rating <= 5", name="ck_plugin_reviews_rating"),
        sa.ForeignKeyConstraint(["plugin_id"], ["plugins.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("plugin_id", "user_id"),
    )

    op.create_table(
        "skill_execution_logs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("skill_id", sa.Integer(), nullable=True),
        sa.Column("skill_key", sa.String(length=100), nullable=False),
        sa.Column("source_type", sa.String(length=20), nullable=False),
        sa.Column("parameters", JSONB, server_default="{}", nullable=False),
        sa.Column("result_summary", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), server_default="0", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("sandbox_level", sa.String(length=20), server_default="basic", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["skill_id"], ["skills.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_skill_execution_logs_tenant_id", "skill_execution_logs", ["tenant_id"])
    op.create_index("ix_skill_execution_logs_skill_key", "skill_execution_logs", ["skill_key"])


def downgrade() -> None:
    """删除插件与 Skill 表。"""
    op.drop_index("ix_skill_execution_logs_skill_key", table_name="skill_execution_logs")
    op.drop_index("ix_skill_execution_logs_tenant_id", table_name="skill_execution_logs")
    op.drop_table("skill_execution_logs")
    op.drop_table("plugin_reviews")
    op.drop_table("skill_configs")
    op.drop_index("ix_skills_source_type", table_name="skills")
    op.drop_index("ix_skills_skill_key", table_name="skills")
    op.drop_table("skills")
    op.drop_index("ix_plugin_installations_tenant_id", table_name="plugin_installations")
    op.drop_table("plugin_installations")
    op.drop_index("ix_plugins_plugin_id", table_name="plugins")
    op.drop_index("ix_plugins_category", table_name="plugins")
    op.drop_table("plugins")
