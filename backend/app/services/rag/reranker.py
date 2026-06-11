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
        self.top_n = top_n
        self.compressor = (
            CohereRerank(
                cohere_api_key=cohere_api_key,
                model="rerank-english-v3.0",
                top_n=top_n,
            )
            if cohere_api_key
            else None
        )
        self._local_reranker: Any | None = None
        self._local_reranker_checked = False

    def _get_local_reranker(self) -> Any | None:
        """加载本地 BGE CrossEncoder，依赖缺失时返回 None。"""
        if self._local_reranker_checked:
            return self._local_reranker

        self._local_reranker_checked = True
        try:
            from sentence_transformers import CrossEncoder

            self._local_reranker = CrossEncoder("BAAI/bge-reranker-base")
            logger.info("已启用本地 BGE 重排序降级")
        except Exception as exc:
            logger.info("sentence-transformers 不可用，跳过本地重排序: %s", exc)
            self._local_reranker = None
        return self._local_reranker

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
                local_reranker = self._get_local_reranker()
                if local_reranker is None:
                    logger.debug("未配置 Cohere 且无本地 BGE，跳过重排序")
                    return base_docs
                pairs = [(query, doc.page_content) for doc in base_docs]
                scores = local_reranker.predict(pairs)
                scored_docs = sorted(
                    zip(base_docs, scores),
                    key=lambda item: float(item[1]),
                    reverse=True,
                )
                return [doc for doc, _ in scored_docs[: self.top_n]]

            # 对已有混合检索结果直接重排，避免重新查询向量库
            results = self.compressor.compress_documents(base_docs, query)
            logger.debug("Cohere 重排序完成 query=%s results=%s", query[:50], len(results))
            return results
        except Exception as exc:
            logger.warning("重排序失败，返回原始结果: %s", exc)
            return base_docs
