"""工作流版本与智能体分享

Revision ID: 011_workflow_versions_agent_share
Revises: 010_custom_tools
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "011"
down_revision: Union[str, None] = "010"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建工作流版本表并扩展智能体分享字段。"""
    op.create_table(
        "workflow_versions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("version", sa.String(length=20), nullable=False),
        sa.Column("graph_definition", JSONB, nullable=False),
        sa.Column("change_note", sa.Text(), nullable=True),
        sa.Column("published_by", sa.Integer(), nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["published_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workflow_versions_workflow_id", "workflow_versions", ["workflow_id"])

    op.add_column("workflows", sa.Column("current_version", sa.String(length=20), nullable=True))
    op.add_column("agents", sa.Column("share_token", sa.String(length=64), nullable=True))
    op.add_column(
        "agents",
        sa.Column("is_share_enabled", sa.Boolean(), server_default="false", nullable=False),
    )
    op.create_index("ix_agents_share_token", "agents", ["share_token"], unique=True)


def downgrade() -> None:
    """回滚版本与分享字段。"""
    op.drop_index("ix_agents_share_token", table_name="agents")
    op.drop_column("agents", "is_share_enabled")
    op.drop_column("agents", "share_token")
    op.drop_column("workflows", "current_version")
    op.drop_index("ix_workflow_versions_workflow_id", table_name="workflow_versions")
    op.drop_table("workflow_versions")
