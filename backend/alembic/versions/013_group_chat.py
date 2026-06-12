"""群聊式多 Agent 协同表

Revision ID: 013
Revises: 012
Create Date: 2026-06-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "013"
down_revision: Union[str, None] = "012"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建群聊会话与消息表。"""
    op.create_table(
        "group_chat_sessions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=True),
        sa.Column("execution_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("task_description", sa.Text(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False),
        sa.Column("progress", sa.Float(), server_default="0", nullable=False),
        sa.Column("current_step", sa.Integer(), server_default="0", nullable=False),
        sa.Column("subtasks", JSONB, server_default="[]", nullable=False),
        sa.Column("deliverables", JSONB, server_default="[]", nullable=False),
        sa.Column("review_result", JSONB, nullable=True),
        sa.Column("review_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=True),
        sa.Column("extra_params", JSONB, server_default="{}", nullable=False),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'reviewing', 'completed', 'failed', 'human_review')",
            name="ck_group_chat_sessions_status",
        ),
        sa.ForeignKeyConstraint(["execution_id"], ["workflow_executions.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_group_chat_sessions_tenant_id", "group_chat_sessions", ["tenant_id"])
    op.create_index("ix_group_chat_sessions_user_id", "group_chat_sessions", ["user_id"])
    op.create_index("ix_group_chat_sessions_status", "group_chat_sessions", ["status"])

    op.create_table(
        "group_chat_messages",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("message_id", sa.String(length=64), nullable=False),
        sa.Column("sender_role", sa.String(length=30), nullable=False),
        sa.Column("message_type", sa.String(length=30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("payload", JSONB, server_default="{}", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["session_id"], ["group_chat_sessions.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("message_id"),
    )
    op.create_index("ix_group_chat_messages_session_id", "group_chat_messages", ["session_id"])
    op.create_index("ix_group_chat_messages_sender_role", "group_chat_messages", ["sender_role"])


def downgrade() -> None:
    """删除群聊表。"""
    op.drop_index("ix_group_chat_messages_sender_role", table_name="group_chat_messages")
    op.drop_index("ix_group_chat_messages_session_id", table_name="group_chat_messages")
    op.drop_table("group_chat_messages")
    op.drop_index("ix_group_chat_sessions_status", table_name="group_chat_sessions")
    op.drop_index("ix_group_chat_sessions_user_id", table_name="group_chat_sessions")
    op.drop_index("ix_group_chat_sessions_tenant_id", table_name="group_chat_sessions")
    op.drop_table("group_chat_sessions")
