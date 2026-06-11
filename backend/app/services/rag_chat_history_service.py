"""
RAG 知识库对话历史服务。
"""

import time
from typing import Any, Optional

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.chat_history import ChatHistory

logger = get_logger(__name__)


class RagChatHistoryService:
    """RAG 对话历史 CRUD。"""

    @staticmethod
    def generate_session_id(kb_id: int) -> str:
        """生成知识库问答 session_id。"""
        return f"kb-{kb_id}-{int(time.time() * 1000)}"

    @staticmethod
    def _validate_session_id(kb_id: int, session_id: str) -> None:
        """校验会话 ID 是否属于当前知识库。"""
        if not session_id.startswith(f"kb-{kb_id}-"):
            raise ValidationError(message="会话 ID 与当前知识库不匹配")

    async def save_messages(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        kb_id: int,
        session_id: str,
        user_query: str,
        assistant_answer: str,
        sources: Optional[list[dict[str, Any]]] = None,
        use_rag: bool = True,
    ) -> None:
        """持久化一轮问答消息。"""
        self._validate_session_id(kb_id, session_id)

        db.add(
            ChatHistory(
                tenant_id=tenant_id,
                user_id=user_id,
                kb_id=kb_id,
                session_id=session_id,
                message_type="user",
                content=user_query,
                meta_data={"use_rag": use_rag},
            )
        )
        db.add(
            ChatHistory(
                tenant_id=tenant_id,
                user_id=user_id,
                kb_id=kb_id,
                session_id=session_id,
                message_type="assistant",
                content=assistant_answer,
                meta_data={"sources": sources or [], "use_rag": use_rag},
            )
        )
        await db.commit()
        logger.info(
            "保存 RAG 对话历史 kb_id=%s session_id=%s user_id=%s",
            kb_id,
            session_id,
            user_id,
        )

    async def get_chat_history(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        kb_id: int,
        session_id: Optional[str] = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """查询知识库对话历史。"""
        stmt = (
            select(ChatHistory)
            .where(
                ChatHistory.tenant_id == tenant_id,
                ChatHistory.user_id == user_id,
                ChatHistory.kb_id == kb_id,
            )
            .order_by(ChatHistory.created_at.asc())
            .limit(limit)
        )
        if session_id:
            self._validate_session_id(kb_id, session_id)
            stmt = stmt.where(ChatHistory.session_id == session_id)
        else:
            stmt = stmt.where(ChatHistory.session_id.like(f"kb-{kb_id}-%"))

        result = await db.execute(stmt)
        records = result.scalars().all()
        return [
            {
                "id": record.id,
                "session_id": record.session_id,
                "message_type": record.message_type,
                "content": record.content,
                "metadata": record.meta_data,
                "created_at": record.created_at.isoformat() if record.created_at else None,
            }
            for record in records
        ]

    async def delete_chat_session(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: int,
        kb_id: int,
        session_id: str,
    ) -> int:
        """删除指定知识库会话的全部历史消息。"""
        self._validate_session_id(kb_id, session_id)

        stmt = delete(ChatHistory).where(
            ChatHistory.tenant_id == tenant_id,
            ChatHistory.user_id == user_id,
            ChatHistory.kb_id == kb_id,
            ChatHistory.session_id == session_id,
        )
        result = await db.execute(stmt)
        deleted_count = int(result.rowcount or 0)
        if deleted_count <= 0:
            raise NotFoundError(message="会话不存在或已删除")
        await db.commit()
        logger.info(
            "删除 RAG 会话历史 kb_id=%s session_id=%s rows=%s",
            kb_id,
            session_id,
            deleted_count,
        )
        return deleted_count


rag_chat_history_service = RagChatHistoryService()
