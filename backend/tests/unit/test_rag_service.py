"""
RAGService 辅助逻辑单元测试。
"""

import pytest

from app.services.rag.rag_service import RAGService


class TestRAGServiceHelpers:
    """RAGService 静态方法与 Redis 异常降级。"""

    def test_parse_progress_key_format(self) -> None:
        assert RAGService._parse_progress_key(42) == "parse_progress:42"

    def test_build_chroma_filters(self) -> None:
        from app.services.rag.rag_service import rag_service

        filters = rag_service._build_chroma_filters(
            {"department": "研发", "file_type": "pdf", "document_id": 3}
        )
        assert filters == {
            "department": "研发",
            "file_type": "pdf",
            "document_id": 3,
        }

    def test_build_chroma_filters_empty(self) -> None:
        from app.services.rag.rag_service import rag_service

        assert rag_service._build_chroma_filters(None) is None
        assert rag_service._build_chroma_filters({}) is None

    def test_collection_name(self) -> None:
        from app.services.rag.rag_service import rag_service

        assert rag_service._collection_name(7) == "kb_7"

    def test_invalidate_retriever(self) -> None:
        from app.services.rag.rag_service import rag_service

        rag_service._retrievers[99] = object()  # type: ignore[assignment]
        rag_service._invalidate_retriever(99)
        assert 99 not in rag_service._retrievers
