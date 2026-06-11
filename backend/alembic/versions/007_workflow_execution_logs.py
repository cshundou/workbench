"""工作流执行日志持久化

Revision ID: 007_workflow_execution_logs
Revises: 006_agent_top_p
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "007_workflow_execution_logs"
down_revision: Union[str, None] = "006_agent_top_p"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为工作流执行记录添加持久化日志字段。"""
    op.add_column(
        "workflow_executions",
        sa.Column(
            "execution_logs",
            JSONB,
            server_default="[]",
            nullable=False,
        ),
    )
    op.add_column(
        "workflow_executions",
        sa.Column(
            "node_statuses",
            JSONB,
            server_default="{}",
            nullable=False,
        ),
    )


def downgrade() -> None:
    """回滚执行日志字段。"""
    op.drop_column("workflow_executions", "node_statuses")
    op.drop_column("workflow_executions", "execution_logs")
