"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-06-10

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """创建所有数据库表与索引。"""
    # 租户表
    op.create_table(
        "tenants",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("domain", sa.String(length=100), nullable=False),
        sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False),
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
        sa.CheckConstraint("status IN (0, 1)", name="ck_tenants_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("domain"),
    )

    # 角色表
    op.create_table(
        "roles",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "permissions",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_roles_tenant_id_name"),
    )

    # 用户表
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("username", sa.String(length=50), nullable=False),
        sa.Column("email", sa.String(length=100), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("role_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.CheckConstraint("status IN (0, 1)", name="ck_users_status"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "email", name="uq_users_tenant_id_email"),
        sa.UniqueConstraint("tenant_id", "username", name="uq_users_tenant_id_username"),
    )
    op.create_index("idx_users_tenant_id", "users", ["tenant_id"])
    op.create_index("idx_users_role_id", "users", ["role_id"])

    # 知识库表
    op.create_table(
        "knowledge_bases",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "embedding_model",
            sa.String(length=50),
            server_default="text-embedding-ada-002",
            nullable=False,
        ),
        sa.Column("chunk_size", sa.Integer(), server_default="512", nullable=False),
        sa.Column("chunk_overlap", sa.Integer(), server_default="100", nullable=False),
        sa.Column("status", sa.SmallInteger(), server_default="1", nullable=False),
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
        sa.CheckConstraint("status IN (0, 1)", name="ck_knowledge_bases_status"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_knowledge_bases_tenant_id_name"),
    )
    op.create_index("idx_knowledge_bases_tenant_id", "knowledge_bases", ["tenant_id"])
    op.create_index("idx_knowledge_bases_owner_id", "knowledge_bases", ["owner_id"])

    # 文档表
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("kb_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("file_type", sa.String(length=50), nullable=False),
        sa.Column("file_size", sa.BigInteger(), nullable=False),
        sa.Column("file_path", sa.String(length=512), nullable=False),
        sa.Column("uploader_id", sa.Integer(), nullable=True),
        sa.Column("status", sa.SmallInteger(), server_default="0", nullable=False),
        sa.Column("total_chunks", sa.Integer(), server_default="0", nullable=False),
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
        sa.CheckConstraint("status IN (0, 1, 2)", name="ck_documents_status"),
        sa.ForeignKeyConstraint(["kb_id"], ["knowledge_bases.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploader_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_documents_tenant_id", "documents", ["tenant_id"])
    op.create_index("idx_documents_kb_id", "documents", ["kb_id"])
    op.create_index("idx_documents_uploader_id", "documents", ["uploader_id"])
    op.create_index("idx_documents_status", "documents", ["status"])

    # 文档分块表
    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("document_id", sa.Integer(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("parent_chunk_id", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("vector_id", sa.String(length=100), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["document_id"], ["documents.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_chunk_id"], ["document_chunks.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "document_id", "chunk_index", name="uq_document_chunks_document_id_chunk_index"
        ),
    )
    op.create_index("idx_document_chunks_document_id", "document_chunks", ["document_id"])
    op.create_index("idx_document_chunks_vector_id", "document_chunks", ["vector_id"])

    # 智能体表
    op.create_table(
        "agents",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("system_prompt", sa.Text(), nullable=False),
        sa.Column(
            "model_name",
            sa.String(length=50),
            server_default="gpt-3.5-turbo",
            nullable=False,
        ),
        sa.Column("temperature", sa.Float(), server_default="0.7", nullable=False),
        sa.Column("max_tokens", sa.Integer(), server_default="2048", nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
        sa.Column(
            "tools",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_agents_tenant_id_name"),
    )
    op.create_index("idx_agents_tenant_id", "agents", ["tenant_id"])
    op.create_index("idx_agents_owner_id", "agents", ["owner_id"])

    # 工作流表
    op.create_table(
        "workflows",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("graph_definition", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("owner_id", sa.Integer(), nullable=True),
        sa.Column("is_public", sa.Boolean(), server_default="false", nullable=False),
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
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_workflows_tenant_id_name"),
    )
    op.create_index("idx_workflows_tenant_id", "workflows", ["tenant_id"])

    # 工作流执行记录表
    op.create_table(
        "workflow_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("workflow_id", sa.Integer(), nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column(
            "input_params",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column("output_result", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'running', 'completed', 'failed', 'interrupted')",
            name="ck_workflow_executions_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "idx_workflow_executions_workflow_id", "workflow_executions", ["workflow_id"]
    )
    op.create_index("idx_workflow_executions_status", "workflow_executions", ["status"])

    # 对话历史表
    op.create_table(
        "chat_histories",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.String(length=100), nullable=False),
        sa.Column("message_type", sa.String(length=20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "message_type IN ('user', 'assistant', 'system', 'tool')",
            name="ck_chat_histories_message_type",
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_chat_histories_tenant_id", "chat_histories", ["tenant_id"])
    op.create_index("idx_chat_histories_user_id", "chat_histories", ["user_id"])
    op.create_index("idx_chat_histories_session_id", "chat_histories", ["session_id"])
    op.create_index("idx_chat_histories_created_at", "chat_histories", ["created_at"])

    # Token 消耗记录表
    op.create_table(
        "token_usage",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=True),
        sa.Column("model_name", sa.String(length=50), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completion_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column("total_tokens", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("idx_token_usage_tenant_id", "token_usage", ["tenant_id"])
    op.create_index("idx_token_usage_user_id", "token_usage", ["user_id"])
    op.create_index("idx_token_usage_created_at", "token_usage", ["created_at"])


def downgrade() -> None:
    """删除所有数据库表。"""
    op.drop_index("idx_token_usage_created_at", table_name="token_usage")
    op.drop_index("idx_token_usage_user_id", table_name="token_usage")
    op.drop_index("idx_token_usage_tenant_id", table_name="token_usage")
    op.drop_table("token_usage")

    op.drop_index("idx_chat_histories_created_at", table_name="chat_histories")
    op.drop_index("idx_chat_histories_session_id", table_name="chat_histories")
    op.drop_index("idx_chat_histories_user_id", table_name="chat_histories")
    op.drop_index("idx_chat_histories_tenant_id", table_name="chat_histories")
    op.drop_table("chat_histories")

    op.drop_index("idx_workflow_executions_status", table_name="workflow_executions")
    op.drop_index("idx_workflow_executions_workflow_id", table_name="workflow_executions")
    op.drop_table("workflow_executions")

    op.drop_index("idx_workflows_tenant_id", table_name="workflows")
    op.drop_table("workflows")

    op.drop_index("idx_agents_owner_id", table_name="agents")
    op.drop_index("idx_agents_tenant_id", table_name="agents")
    op.drop_table("agents")

    op.drop_index("idx_document_chunks_vector_id", table_name="document_chunks")
    op.drop_index("idx_document_chunks_document_id", table_name="document_chunks")
    op.drop_table("document_chunks")

    op.drop_index("idx_documents_status", table_name="documents")
    op.drop_index("idx_documents_uploader_id", table_name="documents")
    op.drop_index("idx_documents_kb_id", table_name="documents")
    op.drop_index("idx_documents_tenant_id", table_name="documents")
    op.drop_table("documents")

    op.drop_index("idx_knowledge_bases_owner_id", table_name="knowledge_bases")
    op.drop_index("idx_knowledge_bases_tenant_id", table_name="knowledge_bases")
    op.drop_table("knowledge_bases")

    op.drop_index("idx_users_role_id", table_name="users")
    op.drop_index("idx_users_tenant_id", table_name="users")
    op.drop_table("users")

    op.drop_table("roles")
    op.drop_table("tenants")
