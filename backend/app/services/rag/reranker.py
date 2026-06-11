"""
重排序 Rerank 层：使用 Cohere Rerank 模型对混合检索结果二次打分。
"""

from typing import Any, Optional

from langchain.schema import Document
from langchain_community.document_compressors import CohereRerank

from app.core.logging import get_logger

logger = get_logger(__name__)


class Reranker:
    """基于 Cohere 的检索结果重排序器，对传入的混合检索文档直接打分。"""

    def __init__(
        self,
        cohere_api_key: Optional[str] = None,
        top_n: int = 5,
    ) -> None:
        self.compressor = (
            CohereRerank(
                cohere_api_key=cohere_api_key,
                model="rerank-english-v3.0",
                top_n=top_n,
            )
            if cohere_api_key
            else None
        )

    def rerank(self, query: str, documents: list[dict[str, Any]]) -> list[Document]:
        """
        对混合检索结果进行重排序。

        Args:
            query: 用户问题。
            documents: 混合检索得到的文档块列表。

        Returns:
            重排序后的 Document 列表。
        """
        base_docs = [
            Document(page_content=doc.get("page_content", ""), metadata=doc.get("metadata", {}))
            for doc in documents
        ]
        if not base_docs:
            return []

        try:
            if not self.compressor:
                logger.debug("未配置 Cohere 密钥，跳过重排序")
                return base_docs

            # 对已有混合检索结果直接重排，避免重新查询向量库
            results = self.compressor.compress_documents(base_docs, query)
            logger.debug("重排序完成 query=%s results=%s", query[:50], len(results))
            return results
        except Exception as exc:
            logger.warning("Cohere 重排序失败，返回原始结果: %s", exc)
            return base_docs
