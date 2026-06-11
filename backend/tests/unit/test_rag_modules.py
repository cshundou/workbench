"""
RAG 子模块单元测试。
"""

from unittest.mock import AsyncMock, MagicMock

import pytest
from langchain.schema import Document

from app.services.rag.answer_generator import AnswerGenerator
from app.services.rag.context_builder import ContextBuilder
from app.services.rag.reranker import Reranker


class TestContextBuilder:
    """上下文拼接。"""

    @pytest.mark.asyncio
    async def test_build_context_empty(self) -> None:
        builder = ContextBuilder(db=AsyncMock())
        context, sources = await builder.build_context([])
        assert context == ""
        assert sources == []

    @pytest.mark.asyncio
    async def test_build_context_with_chunk(self) -> None:
        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        builder = ContextBuilder(db=mock_db)
        chunk = Document(
            page_content="测试内容",
            metadata={
                "document_name": "doc.txt",
                "page_number": 1,
                "chunk_index": 0,
                "document_id": 1,
            },
        )
        context, sources = await builder.build_context([chunk])
        assert "测试内容" in context
        assert len(sources) == 1
        assert sources[0]["document_name"] == "doc.txt"


class TestAnswerGenerator:
    """回答生成器初始化。"""

    def test_init_with_mock_llm(self) -> None:
        user_ctx = MagicMock()
        llm = MagicMock()
        llm.model_name = "gpt-3.5-turbo"
        gen = AnswerGenerator(user_ctx=user_ctx, llm=llm)
        assert gen._model_name == "gpt-3.5-turbo"


class TestReranker:
    """重排序器。"""

    def test_rerank_without_cohere_key(self) -> None:
        reranker = Reranker(cohere_api_key=None)
        docs = [{"page_content": "hello", "metadata": {"id": 1}}]
        results = reranker.rerank("query", docs)
        assert len(results) == 1
        assert results[0].page_content == "hello"
