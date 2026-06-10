"""
双路检索层：向量检索 + BM25 关键词检索，结果融合加权排序。
"""

from typing import Any, Optional

from langchain.retrievers import EnsembleRetriever
from langchain.schema import Document
from langchain_community.retrievers import BM25Retriever
from langchain_community.vectorstores import Chroma

from app.core.logging import get_logger

logger = get_logger(__name__)


class HybridRetriever:
    """混合检索器，融合向量检索与 BM25 检索。"""

    def __init__(self, vector_store: Chroma) -> None:
        self.vector_store = vector_store
        self.vector_retriever = vector_store.as_retriever(search_kwargs={"k": 10})
        self.bm25_retriever: Optional[BM25Retriever] = None
        self.ensemble_retriever: Optional[EnsembleRetriever] = None

    def initialize_bm25(self, documents: list[dict[str, Any]]) -> None:
        """
        初始化 BM25 检索器并构建混合检索器。

        Args:
            documents: 文档列表，每项含 page_content 与 metadata。
        """
        if not documents:
            self.bm25_retriever = None
            self.ensemble_retriever = self.vector_retriever
            logger.warning("BM25 初始化跳过：无可用文档")
            return

        langchain_docs = [
            Document(page_content=doc["page_content"], metadata=doc.get("metadata", {}))
            for doc in documents
        ]
        self.bm25_retriever = BM25Retriever.from_documents(langchain_docs)
        self.bm25_retriever.k = 10
        self.ensemble_retriever = EnsembleRetriever(
            retrievers=[self.bm25_retriever, self.vector_retriever],
            weights=[0.3, 0.7],
        )
        logger.info("BM25 混合检索器初始化完成 documents=%s", len(langchain_docs))

    def retrieve(
        self,
        query: str,
        filters: Optional[dict[str, Any]] = None,
        top_k: int = 5,
    ) -> list[Document]:
        """
        执行混合检索，返回前 top_k 个结果。

        Args:
            query: 检索问题。
            filters: Chroma 元数据过滤条件。
            top_k: 返回结果数量。

        Returns:
            去重后的 LangChain Document 列表。
        """
        if filters:
            self.vector_retriever.search_kwargs["filter"] = filters

        retriever = self.ensemble_retriever or self.vector_retriever
        results = retriever.get_relevant_documents(query)

        seen_ids: set[Any] = set()
        unique_results: list[Document] = []
        for doc in results:
            vector_id = doc.metadata.get("vector_id")
            if vector_id not in seen_ids:
                seen_ids.add(vector_id)
                unique_results.append(doc)
                if len(unique_results) >= top_k:
                    break

        logger.debug("混合检索完成 query=%s results=%s", query[:50], len(unique_results))
        return unique_results
