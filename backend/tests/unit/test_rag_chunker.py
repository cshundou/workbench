"""
RAG 智能分块模块单元测试。
"""

from unittest.mock import MagicMock, patch

from app.services.rag.chunker import IntelligentChunker


def _mock_embeddings() -> MagicMock:
    return MagicMock()


class TestIntelligentChunker:
    """IntelligentChunker 配置与分块行为。"""

    @patch("app.services.rag.chunker.SemanticChunker")
    def test_uses_kb_chunk_size_and_overlap(self, mock_semantic_cls: MagicMock) -> None:
        """分块器应使用知识库配置的 chunk_size / chunk_overlap。"""
        mock_semantic_cls.return_value.split_text.return_value = ["短文本块"]
        chunker = IntelligentChunker(
            embedding_model="text-embedding-ada-002",
            embeddings=_mock_embeddings(),
            chunk_size=256,
            chunk_overlap=50,
        )
        assert chunker.chunk_size == 256
        assert chunker.chunk_overlap == 50
        assert chunker.recursive_splitter._chunk_size == 256
        assert chunker.recursive_splitter._chunk_overlap == 50

    @patch("app.services.rag.chunker.SemanticChunker")
    def test_split_document_returns_chunks(self, mock_semantic_cls: MagicMock) -> None:
        """语义分块后应返回带 metadata 的块列表。"""
        mock_semantic_cls.return_value.split_text.return_value = [
            "第一段内容",
            "第二段内容",
        ]
        chunker = IntelligentChunker(
            embeddings=_mock_embeddings(),
            chunk_size=512,
            chunk_overlap=100,
        )
        result = chunker.split_document("测试文档", {"document_id": 1})
        assert len(result) == 2
        assert result[0]["content"] == "第一段内容"
        assert result[0]["metadata"]["document_id"] == 1
        assert "chunk_index" in result[0]["metadata"]

    @patch("app.services.rag.chunker.SemanticChunker")
    def test_oversized_chunk_gets_recursive_split(
        self, mock_semantic_cls: MagicMock
    ) -> None:
        """超过 chunk_size * 2 的语义块应被递归拆分。"""
        long_text = "A" * 1200
        mock_semantic_cls.return_value.split_text.return_value = [long_text]
        chunker = IntelligentChunker(
            embeddings=_mock_embeddings(),
            chunk_size=512,
            chunk_overlap=100,
        )
        result = chunker.split_document(long_text, {})
        assert len(result) > 1

    @patch("app.services.rag.chunker.SemanticChunker")
    def test_extract_headings_from_markdown(self, mock_semantic_cls: MagicMock) -> None:
        """应能从 Markdown 标题行提取 heading 元数据。"""
        mock_semantic_cls.return_value.split_text.return_value = ["# 标题\n正文内容"]
        chunker = IntelligentChunker(embeddings=_mock_embeddings())
        result = chunker.split_document("# 标题\n正文内容", {})
        assert result[0]["metadata"].get("heading") == "标题"
