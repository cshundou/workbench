"""
RAG 混合检索模块单元测试。
"""

from unittest.mock import MagicMock

from langchain.schema import Document

from app.services.rag.retriever import HybridRetriever


class TestHybridRetriever:
    """HybridRetriever 去重与降级逻辑。"""

    def test_empty_corpus_falls_back_to_vector_only(self) -> None:
        vector_store = MagicMock()
        vector_store.as_retriever.return_value = MagicMock()
        retriever = HybridRetriever(vector_store)
        retriever.initialize_bm25([])
        assert retriever.ensemble_retriever is retriever.vector_retriever

    def test_retrieve_deduplicates_by_vector_id(self) -> None:
        vector_store = MagicMock()
        mock_vs_retriever = MagicMock()
        vector_store.as_retriever.return_value = mock_vs_retriever

        doc1 = Document(page_content="a", metadata={"vector_id": "v1"})
        doc2 = Document(page_content="b", metadata={"vector_id": "v1"})
        doc3 = Document(page_content="c", metadata={"vector_id": "v2"})
        mock_vs_retriever.get_relevant_documents.return_value = [doc1, doc2, doc3]

        retriever = HybridRetriever(vector_store)
        retriever.ensemble_retriever = mock_vs_retriever
        results = retriever.retrieve("query", top_k=5)
        assert len(results) == 2
        ids = {d.metadata["vector_id"] for d in results}
        assert ids == {"v1", "v2"}
