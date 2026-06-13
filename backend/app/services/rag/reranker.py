"""
重排序 Rerank 层：支持 Cohere、已配置大模型 Embedding 或本地 BGE 二次打分。
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Optional

from langchain.schema import Document

from app.core.logging import get_logger
from app.services.user_key_context import (
    LLM_PROVIDERS,
    RERANK_MODE_AUTO,
    RERANK_MODE_COHERE,
    RERANK_MODE_OFF,
    create_embeddings_for_provider,
)

if TYPE_CHECKING:
    from app.services.user_key_context import UserKeyContext

logger = get_logger(__name__)

RERANK_COHERE_DEFAULT_MODEL = "rerank-multilingual-v3.0"


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    """计算两个向量的余弦相似度。"""
    dot = sum(a * b for a, b in zip(left, right))
    norm_left = sum(a * a for a in left) ** 0.5
    norm_right = sum(b * b for b in right) ** 0.5
    if norm_left == 0 or norm_right == 0:
        return 0.0
    return dot / (norm_left * norm_right)


class Reranker:
    """检索结果重排序器，对传入的混合检索文档直接打分。"""

    def __init__(
        self,
        user_ctx: Optional["UserKeyContext"] = None,
        mode: str = RERANK_MODE_AUTO,
        top_n: int = 5,
        cohere_api_key: Optional[str] = None,
        cohere_model: str = RERANK_COHERE_DEFAULT_MODEL,
        embedding_model: Optional[str] = None,
    ) -> None:
        self.user_ctx = user_ctx
        self.mode = mode
        self.top_n = top_n
        self.cohere_api_key = cohere_api_key
        self.cohere_model = cohere_model
        self.embedding_model = embedding_model
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

    def _rerank_with_cohere(
        self,
        query: str,
        base_docs: list[Document],
    ) -> list[Document]:
        """使用 Cohere Rerank API 对文档列表重排。"""
        import cohere

        client = cohere.ClientV2(api_key=self.cohere_api_key)
        response = client.rerank(
            model=self.cohere_model,
            query=query,
            documents=[doc.page_content for doc in base_docs],
            top_n=min(self.top_n, len(base_docs)),
        )
        ranked: list[Document] = []
        for item in response.results:
            ranked.append(base_docs[item.index])
        return ranked

    def _rerank_with_embedding(
        self,
        query: str,
        base_docs: list[Document],
        llm_provider: str,
    ) -> list[Document]:
        """使用已配置大模型的 Embedding 接口对候选文档重新打分。"""
        if self.user_ctx is None:
            raise ValueError("缺少用户密钥上下文，无法使用大模型 Embedding 重排序")

        embeddings = create_embeddings_for_provider(
            self.user_ctx,
            llm_provider,
            model_name=self.embedding_model,
        )
        query_vector = embeddings.embed_query(query)
        doc_vectors = embeddings.embed_documents([doc.page_content for doc in base_docs])
        scored_docs = sorted(
            zip(base_docs, doc_vectors),
            key=lambda item: _cosine_similarity(query_vector, item[1]),
            reverse=True,
        )
        return [doc for doc, _ in scored_docs[: self.top_n]]

    def _rerank_with_local_bge(
        self,
        query: str,
        base_docs: list[Document],
    ) -> list[Document] | None:
        """使用本地 BGE CrossEncoder 重排，不可用时返回 None。"""
        local_reranker = self._get_local_reranker()
        if local_reranker is None:
            return None

        pairs = [(query, doc.page_content) for doc in base_docs]
        scores = local_reranker.predict(pairs)
        scored_docs = sorted(
            zip(base_docs, scores),
            key=lambda item: float(item[1]),
            reverse=True,
        )
        return [doc for doc, _ in scored_docs[: self.top_n]]

    def _resolve_llm_provider_for_mode(self) -> Optional[str]:
        """解析当前模式对应的大模型提供商。"""
        if self.mode in LLM_PROVIDERS:
            return self.mode
        if self.user_ctx is None:
            return None

        if self.mode == RERANK_MODE_AUTO:
            try:
                return self.user_ctx.get_embedding_provider().provider
            except Exception:
                return None
        return None

    def _try_cohere(self, query: str, base_docs: list[Document]) -> list[Document] | None:
        """尝试 Cohere 重排序。"""
        if not self.cohere_api_key:
            return None
        results = self._rerank_with_cohere(query, base_docs)
        logger.debug("Cohere 重排序完成 query=%s results=%s", query[:50], len(results))
        return results

    def _try_embedding(self, query: str, base_docs: list[Document]) -> list[Document] | None:
        """尝试大模型 Embedding 重排序。"""
        llm_provider = self._resolve_llm_provider_for_mode()
        if llm_provider is None or self.user_ctx is None:
            return None
        if llm_provider not in self.user_ctx.keys:
            return None

        results = self._rerank_with_embedding(query, base_docs, llm_provider)
        logger.debug(
            "Embedding 重排序完成 provider=%s query=%s results=%s",
            llm_provider,
            query[:50],
            len(results),
        )
        return results

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

        if self.mode == RERANK_MODE_OFF:
            return base_docs[: self.top_n]

        try:
            if self.mode == RERANK_MODE_COHERE:
                cohere_results = self._try_cohere(query, base_docs)
                if cohere_results is not None:
                    return cohere_results
                embedding_results = self._try_embedding(query, base_docs)
                if embedding_results is not None:
                    return embedding_results
            elif self.mode in LLM_PROVIDERS:
                embedding_results = self._try_embedding(query, base_docs)
                if embedding_results is not None:
                    return embedding_results
            elif self.mode == RERANK_MODE_AUTO:
                cohere_results = self._try_cohere(query, base_docs)
                if cohere_results is not None:
                    return cohere_results
                embedding_results = self._try_embedding(query, base_docs)
                if embedding_results is not None:
                    return embedding_results
            else:
                logger.warning("未知重排序模式 mode=%s，回退到自动策略", self.mode)

            local_results = self._rerank_with_local_bge(query, base_docs)
            if local_results is not None:
                return local_results

            logger.debug("无可用重排序后端，返回混合检索原始顺序")
            return base_docs[: self.top_n]
        except Exception as exc:
            logger.warning("重排序失败，返回原始结果: %s", exc)
            return base_docs[: self.top_n]
