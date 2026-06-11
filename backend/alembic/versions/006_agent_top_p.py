"""智能体 top_p 参数

Revision ID: 006_agent_top_p
Revises: 005_rag_chat_kb_id
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_agent_top_p"
down_revision: Union[str, None] = "005_rag_chat_kb_id"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 agents 表增加 top_p 字段。"""
    op.add_column(
        "agents",
        sa.Column("top_p", sa.Float(), server_default="1.0", nullable=False),
    )


def downgrade() -> None:
    """回滚 top_p 字段。"""
    op.drop_column("agents", "top_p")
