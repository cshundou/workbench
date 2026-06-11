"""
重排序 Rerank 层：使用 Cohere Rerank 模型进行二次排序。
"""

from typing import Any, Optional

from langchain.retrievers import ContextualCompressionRetriever
from langchain.retrievers.document_compressors import CohereRerank
from langchain.schema import BaseRetriever, Document

from app.core.logging import get_logger

logger = get_logger(__name__)


class Reranker:
    """基于 Cohere 的检索结果重排序器。"""

    def __init__(
        self,
        base_retriever: BaseRetriever,
        cohere_api_key: Optional[str] = None,
    ) -> None:
        self.cohere_api_key = cohere_api_key
        self.base_retriever = base_retriever
        self.compressor = CohereRerank(
            cohere_api_key=cohere_api_key,
            model="rerank-english-v3.0",
            top_n=5,
        ) if cohere_api_key else None
        self.compression_retriever = (
            ContextualCompressionRetriever(
                base_compressor=self.compressor,
                base_retriever=base_retriever,
            )
            if self.compressor
            else None
        )

    def rerank(self, query: str, documents: list[dict[str, Any]]) -> list[Document]:
        """
        对检索结果进行重排序。

        Args:
            query: 用户问题。
            documents: 检索到的文档块（未直接使用，由 base_retriever 提供）。

        Returns:
            重排序后的 Document 列表。
        """
        try:
            if not self.compression_retriever:
                logger.debug("未配置 Cohere 密钥，跳过重排序")
                return [
                    Document(page_content=doc.get("page_content", ""), metadata=doc.get("metadata", {}))
                    for doc in documents
                ]
            results = self.compression_retriever.get_relevant_documents(query)
            logger.debug("重排序完成 query=%s results=%s", query[:50], len(results))
            return results
        except Exception as exc:
            logger.warning("Cohere 重排序失败，返回原始结果: %s", exc)
            return [
                Document(page_content=doc.get("page_content", ""), metadata=doc.get("metadata", {}))
                for doc in documents
            ]
