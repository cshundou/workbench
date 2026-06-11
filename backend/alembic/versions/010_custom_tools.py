"""自定义工具表

Revision ID: 010_custom_tools
Revises: 009_agent_model_priorities
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "010_custom_tools"
down_revision: Union[str, None] = "009_agent_model_priorities"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 custom_tools 表。"""
    op.create_table(
        "custom_tools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("parameters_schema", JSONB, nullable=False),
        sa.Column("invoke_url", sa.String(length=512), nullable=False),
        sa.Column("auth_type", sa.String(length=20), server_default="none", nullable=False),
        sa.Column("auth_token", sa.String(length=512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_custom_tools_tenant_id", "custom_tools", ["tenant_id"])
    op.create_index("ix_custom_tools_owner_id", "custom_tools", ["owner_id"])


def downgrade() -> None:
    """删除 custom_tools 表。"""
    op.drop_index("ix_custom_tools_owner_id", table_name="custom_tools")
    op.drop_index("ix_custom_tools_tenant_id", table_name="custom_tools")
    op.drop_table("custom_tools")
