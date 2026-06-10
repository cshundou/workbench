"""
上下文拼接层：父子块检索机制，保证上下文完整性。
"""

from typing import Any

from langchain.schema import Document
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.document_chunk import DocumentChunk

logger = get_logger(__name__)


class ContextBuilder:
    """检索结果上下文构建器。"""

    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def build_context(
        self,
        retrieved_chunks: list[Document],
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        构建完整上下文，包含父子块信息和引用来源。

        Args:
            retrieved_chunks: 检索到的 LangChain Document 列表。

        Returns:
            (上下文字符串, 引用来源列表)。
        """
        context_parts: list[str] = []
        sources: list[dict[str, Any]] = []

        for index, chunk in enumerate(retrieved_chunks):
            chunk_metadata = chunk.metadata
            parent_chunk_db_id = chunk_metadata.get("parent_chunk_db_id")

            if parent_chunk_db_id is not None:
                stmt = select(DocumentChunk).where(DocumentChunk.id == parent_chunk_db_id)
                result = await self.db.execute(stmt)
                parent_chunk = result.scalar_one_or_none()

                if parent_chunk:
                    preview = parent_chunk.content[:200]
                    context_parts.append(f"【上下文：{preview}...】")

            context_parts.append(f"[{index + 1}] {chunk.page_content}")

            sources.append(
                {
                    "id": index + 1,
                    "document_name": chunk_metadata.get("document_name", "未知文档"),
                    "page_number": chunk_metadata.get("page_number", "未知"),
                    "chunk_index": chunk_metadata.get("chunk_index", "未知"),
                    "document_id": chunk_metadata.get("document_id"),
                }
            )
            context_parts.append("---")

        context = "\n\n".join(context_parts)
        logger.debug("上下文构建完成 sources=%s", len(sources))
        return context, sources
