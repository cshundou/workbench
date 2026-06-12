"""动态智能团队：专业角色库与团队模板表

Revision ID: 017
Revises: 016
Create Date: 2026-06-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建专业角色与团队模板表。"""
    op.create_table(
        "professional_roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("role_id", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("avatar", sa.String(length=20), server_default="🤖", nullable=False),
        sa.Column("category", sa.String(length=50), server_default="general", nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column("tools", JSONB, server_default="[]", nullable=False),
        sa.Column("responsibility", sa.Text(), nullable=False),
        sa.Column("color", sa.String(length=20), server_default="#1677FF", nullable=False),
        sa.Column("is_preset", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_builtin", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "role_id", name="uq_professional_roles_tenant_role_id"),
    )
    op.create_index("ix_professional_roles_role_id", "professional_roles", ["role_id"])
    op.create_index("ix_professional_roles_tenant_id", "professional_roles", ["tenant_id"])

    op.create_table(
        "team_templates",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("scenario", sa.String(length=50), server_default="general", nullable=False),
        sa.Column("team_config", JSONB, server_default="{}", nullable=False),
        sa.Column("is_official", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_team_templates_tenant_id", "team_templates", ["tenant_id"])
    op.create_index("ix_team_templates_user_id", "team_templates", ["user_id"])


def downgrade() -> None:
    """删除动态团队相关表。"""
    op.drop_index("ix_team_templates_user_id", table_name="team_templates")
    op.drop_index("ix_team_templates_tenant_id", table_name="team_templates")
    op.drop_table("team_templates")
    op.drop_index("ix_professional_roles_tenant_id", table_name="professional_roles")
    op.drop_index("ix_professional_roles_role_id", table_name="professional_roles")
    op.drop_table("professional_roles")
