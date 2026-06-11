"""RAG 对话历史 kb_id 字段

Revision ID: 005_rag_chat_kb_id
Revises: 004_phase3
Create Date: 2026-06-11
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_rag_chat_kb_id"
down_revision: Union[str, None] = "004_phase3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """为 chat_histories 增加 kb_id 以区分 RAG 会话。"""
    op.add_column(
        "chat_histories",
        sa.Column("kb_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_chat_histories_kb_id",
        "chat_histories",
        "knowledge_bases",
        ["kb_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("idx_chat_histories_kb_id", "chat_histories", ["kb_id"])


def downgrade() -> None:
    """回滚 kb_id 字段。"""
    op.drop_index("idx_chat_histories_kb_id", table_name="chat_histories")
    op.drop_constraint("fk_chat_histories_kb_id", "chat_histories", type_="foreignkey")
    op.drop_column("chat_histories", "kb_id")
