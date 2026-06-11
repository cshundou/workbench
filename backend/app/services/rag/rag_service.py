"""
RAG 编排服务：串联 7 层架构，管理 Chroma 向量库与增量更新。
"""

import asyncio
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from langchain.schema import Document
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.logging import get_logger
from app.models.document import Document as DocumentModel
from app.models.document_chunk import DocumentChunk
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.rag.answer_generator import AnswerGenerator
from app.services.rag.chunker import IntelligentChunker
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.document_loader import DocumentLoader
from app.services.rag.reranker import Reranker
from app.services.rag.retriever import HybridRetriever
from app.services.user_key_context import UserKeyContext, create_embeddings, user_key_resolver
from app.services.token_usage_service import token_usage_service

logger = get_logger(__name__)

# 文档解析进度缓存（document_id -> progress info）
_parse_progress: dict[int, dict[str, Any]] = {}


class RAGService:
    """增强 RAG 编排服务。"""

    def __init__(self) -> None:
        self.document_loader = DocumentLoader()
        self._vector_stores: dict[int, Chroma] = {}
        self._retrievers: dict[int, HybridRetriever] = {}
        self._embeddings_cache: dict[str, OpenAIEmbeddings] = {}
        Path(settings.chroma_persist_dir).mkdir(parents=True, exist_ok=True)

    def _get_embeddings(
        self,
        user_ctx: UserKeyContext,
        model_name: str,
    ) -> OpenAIEmbeddings:
        """按用户与模型名缓存 Embeddings 实例。"""
        cache_key = f"{user_ctx.user_id}:{model_name}"
        if cache_key not in self._embeddings_cache:
            self._embeddings_cache[cache_key] = create_embeddings(user_ctx, model_name)
        return self._embeddings_cache[cache_key]

    def _collection_name(self, kb_id: int) -> str:
        """生成 Chroma 集合名称。"""
        return f"kb_{kb_id}"

    def get_vector_store(
        self,
        kb_id: int,
        embedding_model: str,
        user_ctx: UserKeyContext,
    ) -> Chroma:
        """
        获取或创建知识库对应的 Chroma 向量存储。

        Args:
            kb_id: 知识库 ID。
            embedding_model: 嵌入模型名称。

        Returns:
            Chroma 向量存储实例。
        """
        if kb_id not in self._vector_stores:
            embeddings = self._get_embeddings(user_ctx, embedding_model)
            self._vector_stores[kb_id] = Chroma(
                collection_name=self._collection_name(kb_id),
                embedding_function=embeddings,
                persist_directory=settings.chroma_persist_dir,
            )
        return self._vector_stores[kb_id]

    async def _get_hybrid_retriever(
        self,
        db: AsyncSession,
        kb: KnowledgeBase,
        user_ctx: UserKeyContext,
    ) -> HybridRetriever:
        """获取或初始化混合检索器（含 BM25 语料）。"""
        vector_store = self.get_vector_store(kb.id, kb.embedding_model, user_ctx)

        if kb.id not in self._retrievers:
            retriever = HybridRetriever(vector_store)
            corpus = await self._load_bm25_corpus(db, kb.id)
            retriever.initialize_bm25(corpus)
            self._retrievers[kb.id] = retriever
        return self._retrievers[kb.id]

    async def _load_bm25_corpus(
        self,
        db: AsyncSession,
        kb_id: int,
    ) -> list[dict[str, Any]]:
        """从数据库加载 BM25 语料。"""
        stmt = (
            select(DocumentChunk)
            .join(DocumentModel, DocumentChunk.document_id == DocumentModel.id)
            .where(DocumentModel.kb_id == kb_id, DocumentModel.status == 1)
        )
        result = await db.execute(stmt)
        chunks = result.scalars().all()
        return [
            {
                "page_content": chunk.content,
                "metadata": {**chunk.meta_data, "vector_id": chunk.vector_id},
            }
            for chunk in chunks
        ]

    def _invalidate_retriever(self, kb_id: int) -> None:
        """文档变更后使检索器缓存失效。"""
        self._retrievers.pop(kb_id, None)

    @staticmethod
    def set_parse_progress(
        document_id: int,
        progress: int,
        message: str,
        status: str = "processing",
    ) -> None:
        """更新文档解析进度。"""
        _parse_progress[document_id] = {
            "document_id": document_id,
            "progress": progress,
            "message": message,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }

    @staticmethod
    def get_parse_progress(document_id: int) -> Optional[dict[str, Any]]:
        """获取文档解析进度。"""
        return _parse_progress.get(document_id)

    @staticmethod
    def clear_parse_progress(document_id: int) -> None:
        """清除文档解析进度缓存。"""
        _parse_progress.pop(document_id, None)

    def _build_chunk_metadata(
        self,
        base_metadata: dict[str, Any],
        kb: KnowledgeBase,
        document: DocumentModel,
        uploader: Optional[User],
    ) -> dict[str, Any]:
        """元数据增强层：为分块附加完整元数据。"""
        department = ""
        if uploader and uploader.role:
            department = uploader.role.name

        return {
            **base_metadata,
            "document_id": document.id,
            "document_name": document.name,
            "kb_id": kb.id,
            "kb_name": kb.name,
            "uploader_id": document.uploader_id,
            "uploader_name": uploader.username if uploader else "未知",
            "department": department,
            "tags": base_metadata.get("tags", []),
            "created_at": document.created_at.isoformat() if document.created_at else "",
            "file_type": document.file_type,
        }

    async def parse_document(
        self,
        db: AsyncSession,
        document_id: int,
        user_id: int,
        tenant_id: int,
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        异步解析文档：加载、分块、向量化并增量写入 Chroma。

        Args:
            db: 数据库会话。
            document_id: 文档 ID。
            user_id: 上传者用户 ID（用于加载 API 密钥）。
            tenant_id: 租户 ID。
            tags: 文档标签列表。
        """
        user_ctx = await user_key_resolver.load_context(db, user_id, tenant_id)
        user_ctx.get_embedding_provider()

        self.set_parse_progress(document_id, 5, "开始解析文档")

        stmt = (
            select(DocumentModel)
            .options(
                selectinload(DocumentModel.knowledge_base),
                selectinload(DocumentModel.uploader).selectinload(User.role),
            )
            .where(DocumentModel.id == document_id)
        )
        result = await db.execute(stmt)
        document = result.scalar_one_or_none()
        if document is None:
            raise NotFoundError(message="文档不存在")

        kb = document.knowledge_base
        if kb is None:
            raise NotFoundError(message="知识库不存在")

        try:
            self.set_parse_progress(document_id, 15, "加载文档内容")
            content = self.document_loader.load_document(document.file_path, document.file_type)

            base_metadata: dict[str, Any] = {"tags": tags or []}
            embeddings = self._get_embeddings(user_ctx, kb.embedding_model)
            chunker = IntelligentChunker(
                embedding_model=kb.embedding_model,
                embeddings=embeddings,
            )
            self.set_parse_progress(document_id, 35, "智能分块中")
            raw_chunks = chunker.split_document(content, base_metadata)

            # 删除该文档旧分块（增量更新：仅重建当前文档）
            await self._delete_document_vectors(db, document, user_ctx)

            vector_store = self.get_vector_store(kb.id, kb.embedding_model, user_ctx)
            parent_db_ids: dict[int, int] = {}
            saved_count = 0
            total = len(raw_chunks)

            for seq_index, raw_chunk in enumerate(raw_chunks):
                enriched_metadata = self._build_chunk_metadata(
                    raw_chunk["metadata"],
                    kb,
                    document,
                    document.uploader,
                )
                parent_semantic_id = enriched_metadata.get("parent_chunk_id")
                parent_db_id: Optional[int] = None

                if parent_semantic_id is not None and "." not in str(
                    enriched_metadata.get("chunk_index", "")
                ):
                    parent_db_id = parent_db_ids.get(int(parent_semantic_id))
                elif parent_semantic_id is not None:
                    parent_db_id = parent_db_ids.get(int(parent_semantic_id))

                vector_id = f"doc_{document.id}_chunk_{uuid.uuid4().hex[:12]}"
                chunk_index_int = seq_index

                db_chunk = DocumentChunk(
                    document_id=document.id,
                    chunk_index=chunk_index_int,
                    parent_chunk_id=parent_db_id,
                    content=raw_chunk["content"],
                    meta_data=enriched_metadata,
                    vector_id=vector_id,
                )
                db.add(db_chunk)
                await db.flush()

                chunk_index_str = str(enriched_metadata.get("chunk_index", ""))
                if "." not in chunk_index_str:
                    parent_db_ids[int(chunk_index_str)] = db_chunk.id

                chroma_metadata = {
                    **enriched_metadata,
                    "vector_id": vector_id,
                    "parent_chunk_db_id": parent_db_id,
                    "chunk_db_id": db_chunk.id,
                }
                vector_store.add_texts(
                    texts=[raw_chunk["content"]],
                    metadatas=[chroma_metadata],
                    ids=[vector_id],
                )
                saved_count += 1
                progress = 35 + int((saved_count / max(total, 1)) * 55)
                self.set_parse_progress(document_id, progress, f"向量化中 ({saved_count}/{total})")

            document.status = 1
            document.total_chunks = saved_count
            self._invalidate_retriever(kb.id)
            vector_store.persist()

            self.set_parse_progress(document_id, 100, "解析完成", status="completed")
            logger.info(
                "文档解析完成 document_id=%s chunks=%s kb_id=%s",
                document_id,
                saved_count,
                kb.id,
            )
        except Exception as exc:
            document.status = 2
            self.set_parse_progress(
                document_id,
                0,
                f"解析失败: {exc}",
                status="failed",
            )
            logger.error("文档解析失败 document_id=%s error=%s", document_id, exc)
            raise

    async def _delete_document_vectors(
        self,
        db: AsyncSession,
        document: DocumentModel,
        user_ctx: UserKeyContext,
    ) -> None:
        """删除文档在向量库与数据库中的分块（增量更新基础）。"""
        stmt = select(DocumentChunk).where(DocumentChunk.document_id == document.id)
        result = await db.execute(stmt)
        chunks = result.scalars().all()

        kb_stmt = select(KnowledgeBase).where(KnowledgeBase.id == document.kb_id)
        kb = (await db.execute(kb_stmt)).scalar_one_or_none()
        if chunks and kb:
            vector_store = self.get_vector_store(kb.id, kb.embedding_model, user_ctx)
            vector_ids = [chunk.vector_id for chunk in chunks]
            try:
                vector_store.delete(ids=vector_ids)
                vector_store.persist()
            except Exception as exc:
                logger.warning("删除向量失败 document_id=%s: %s", document.id, exc)

        await db.execute(
            delete(DocumentChunk).where(DocumentChunk.document_id == document.id)
        )
        document.total_chunks = 0
        self._invalidate_retriever(document.kb_id)

    async def delete_document_vectors(
        self,
        db: AsyncSession,
        document: DocumentModel,
        user_ctx: UserKeyContext,
    ) -> None:
        """对外暴露的文档向量删除接口。"""
        await self._delete_document_vectors(db, document, user_ctx)

    def _build_chroma_filters(self, filters: Optional[dict[str, Any]]) -> Optional[dict[str, Any]]:
        """将 API 过滤条件转换为 Chroma 元数据过滤格式。"""
        if not filters:
            return None

        chroma_filter: dict[str, Any] = {}
        if filters.get("department"):
            chroma_filter["department"] = filters["department"]
        if filters.get("file_type"):
            chroma_filter["file_type"] = filters["file_type"]
        if filters.get("document_id"):
            chroma_filter["document_id"] = filters["document_id"]
        if filters.get("tags"):
            chroma_filter["tags"] = {"$contains": filters["tags"]}

        return chroma_filter or None

    async def retrieve(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        user_ctx: UserKeyContext,
        top_k: int = 5,
        filters: Optional[dict[str, Any]] = None,
    ) -> list[dict[str, Any]]:
        """
        执行完整检索流水线：混合检索 -> 重排序。
        """
        user_ctx.get_embedding_provider()
        kb = await self._get_knowledge_base(db, kb_id)
        hybrid_retriever = await self._get_hybrid_retriever(db, kb, user_ctx)
        chroma_filters = self._build_chroma_filters(filters)

        retrieved = hybrid_retriever.retrieve(query, filters=chroma_filters, top_k=top_k * 2)

        doc_dicts = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in retrieved
        ]

        cohere_key = user_ctx.get_provider("cohere")
        reranker = Reranker(
            hybrid_retriever.vector_retriever,
            cohere_api_key=cohere_key.api_key if cohere_key else None,
        )
        reranked = reranker.rerank(query, doc_dicts)
        final_docs = reranked[:top_k]

        return [
            {
                "content": doc.page_content,
                "metadata": doc.metadata,
                "score": doc.metadata.get("relevance_score"),
            }
            for doc in final_docs
        ]

    async def answer(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        user_ctx: UserKeyContext,
        top_k: int = 5,
        filters: Optional[dict[str, Any]] = None,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """完整 RAG 问答：检索 -> 上下文构建 -> 生成回答。"""
        user_ctx.get_llm_provider()
        kb = await self._get_knowledge_base(db, kb_id)
        hybrid_retriever = await self._get_hybrid_retriever(db, kb, user_ctx)
        chroma_filters = self._build_chroma_filters(filters)

        retrieved = hybrid_retriever.retrieve(query, filters=chroma_filters, top_k=top_k * 2)
        doc_dicts = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in retrieved
        ]
        cohere_key = user_ctx.get_provider("cohere")
        reranker = Reranker(
            hybrid_retriever.vector_retriever,
            cohere_api_key=cohere_key.api_key if cohere_key else None,
        )
        reranked = reranker.rerank(query, doc_dicts)[:top_k]

        context_builder = ContextBuilder(db)
        context, sources = await context_builder.build_context(reranked)

        generator = AnswerGenerator(user_ctx)
        result = generator.generate_answer(query, context, sources)

        if tenant_id is not None:
            await token_usage_service.record_from_langchain_response(
                db=db,
                tenant_id=tenant_id,
                user_id=user_id,
                model_name=result.get("model_name", generator.model_name),
                response=result.get("llm_response"),
            )

        return {
            "answer": result["answer"],
            "sources": result["sources"],
        }

    async def answer_stream(
        self,
        db: AsyncSession,
        kb_id: int,
        query: str,
        user_ctx: UserKeyContext,
        top_k: int = 5,
        filters: Optional[dict[str, Any]] = None,
        tenant_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        """流式 RAG 问答生成器。"""
        user_ctx.get_llm_provider()
        kb = await self._get_knowledge_base(db, kb_id)
        hybrid_retriever = await self._get_hybrid_retriever(db, kb, user_ctx)
        chroma_filters = self._build_chroma_filters(filters)

        retrieved = hybrid_retriever.retrieve(query, filters=chroma_filters, top_k=top_k * 2)
        doc_dicts = [
            {"page_content": doc.page_content, "metadata": doc.metadata}
            for doc in retrieved
        ]
        cohere_key = user_ctx.get_provider("cohere")
        reranker = Reranker(
            hybrid_retriever.vector_retriever,
            cohere_api_key=cohere_key.api_key if cohere_key else None,
        )
        reranked = reranker.rerank(query, doc_dicts)[:top_k]

        context_builder = ContextBuilder(db)
        context, sources = await context_builder.build_context(reranked)

        generator = AnswerGenerator(user_ctx)
        async for event in generator.generate_answer_stream(query, context, sources):
            if event.get("type") == "usage" and tenant_id is not None:
                await token_usage_service.record_from_langchain_response(
                    db=db,
                    tenant_id=tenant_id,
                    user_id=user_id,
                    model_name=event.get("model_name", generator.model_name),
                    response=event.get("llm_response"),
                )
                continue
            yield event

    async def _get_knowledge_base(self, db: AsyncSession, kb_id: int) -> KnowledgeBase:
        """查询知识库实体。"""
        stmt = select(KnowledgeBase).where(KnowledgeBase.id == kb_id)
        result = await db.execute(stmt)
        kb = result.scalar_one_or_none()
        if kb is None:
            raise NotFoundError(message="知识库不存在")
        if kb.status != 1:
            raise ValidationError(message="知识库已禁用")
        return kb

    async def run_parse_document_task(
        self,
        document_id: int,
        user_id: int,
        tenant_id: int,
        tags: Optional[list[str]] = None,
    ) -> None:
        """
        后台异步任务：在独立会话中解析文档。
        """
        from app.core.database import async_session_factory

        for attempt in range(10):
            async with async_session_factory() as db:
                stmt = select(DocumentModel.id).where(DocumentModel.id == document_id)
                exists = (await db.execute(stmt)).scalar_one_or_none()
                if exists is not None:
                    try:
                        await self.parse_document(
                            db, document_id, user_id, tenant_id, tags=tags
                        )
                        await db.commit()
                        return
                    except Exception as exc:
                        await db.rollback()
                        logger.error(
                            "后台解析任务失败 document_id=%s: %s",
                            document_id,
                            exc,
                        )
                        return
            await asyncio.sleep(0.3 * (attempt + 1))

        logger.error("后台解析任务超时，文档记录未找到 document_id=%s", document_id)

    def schedule_parse_document(
        self,
        document_id: int,
        user_id: int,
        tenant_id: int,
        tags: Optional[list[str]] = None,
    ) -> None:
        """调度文档解析后台任务。"""
        asyncio.create_task(
            self.run_parse_document_task(document_id, user_id, tenant_id, tags=tags)
        )
        logger.info("已调度文档解析任务 document_id=%s", document_id)


rag_service = RAGService()
