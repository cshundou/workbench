"""三期增强：工作流状态、租户 Token 配额

Revision ID: 004_phase3
Revises: 003_audit_logs
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_phase3"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """添加 workflows.status 与 tenants.monthly_token_limit。"""
    op.add_column(
        "workflows",
        sa.Column("status", sa.String(length=16), server_default="draft", nullable=False),
    )
    op.add_column(
        "workflows",
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "tenants",
        sa.Column("monthly_token_limit", sa.Integer(), server_default="0", nullable=False),
    )


def downgrade() -> None:
    """回滚三期增强字段。"""
    op.drop_column("tenants", "monthly_token_limit")
    op.drop_column("workflows", "published_at")
    op.drop_column("workflows", "status")
