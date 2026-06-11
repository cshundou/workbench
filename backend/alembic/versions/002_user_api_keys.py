"""user api keys table

Revision ID: 002
Revises: 001
Create Date: 2026-06-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建 user_api_keys 表。"""
    op.create_table(
        "user_api_keys",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("provider", sa.String(length=50), nullable=False),
        sa.Column("api_key", sa.String(length=512), nullable=False),
        sa.Column("base_url", sa.String(length=255), nullable=True),
        sa.Column("model_name", sa.String(length=50), nullable=True),
        sa.Column("is_default", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_valid", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("last_validated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "provider", name="uq_user_api_keys_user_id_provider"),
    )
    op.create_index("idx_user_api_keys_user_id", "user_api_keys", ["user_id"])
    op.create_index("idx_user_api_keys_tenant_id", "user_api_keys", ["tenant_id"])


def downgrade() -> None:
    """删除 user_api_keys 表。"""
    op.drop_index("idx_user_api_keys_tenant_id", table_name="user_api_keys")
    op.drop_index("idx_user_api_keys_user_id", table_name="user_api_keys")
    op.drop_table("user_api_keys")
