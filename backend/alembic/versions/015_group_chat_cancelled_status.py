"""群聊会话增加 cancelled 状态

Revision ID: 015
Revises: 014
Create Date: 2026-06-13
"""

from typing import Sequence, Union

from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """扩展群聊会话 status 约束，支持 cancelled。"""
    op.drop_constraint(
        "ck_group_chat_sessions_status",
        "group_chat_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_group_chat_sessions_status",
        "group_chat_sessions",
        "status IN ('pending', 'running', 'reviewing', 'completed', 'failed', 'human_review', 'cancelled')",
    )


def downgrade() -> None:
    """回滚 cancelled 状态约束。"""
    op.drop_constraint(
        "ck_group_chat_sessions_status",
        "group_chat_sessions",
        type_="check",
    )
    op.create_check_constraint(
        "ck_group_chat_sessions_status",
        "group_chat_sessions",
        "status IN ('pending', 'running', 'reviewing', 'completed', 'failed', 'human_review')",
    )
