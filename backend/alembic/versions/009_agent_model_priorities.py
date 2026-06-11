"""智能体模型降级优先级

Revision ID: 009_agent_model_priorities
Revises: 008_user_login_ip
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "009_agent_model_priorities"
down_revision: Union[str, None] = "008_user_login_ip"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 agents 表增加 model_priorities 字段。"""
    op.add_column(
        "agents",
        sa.Column(
            "model_priorities",
            JSONB,
            nullable=False,
            server_default="[]",
        ),
    )


def downgrade() -> None:
    """回滚 model_priorities 字段。"""
    op.drop_column("agents", "model_priorities")
