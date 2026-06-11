"""
向量存储抽象层：支持 Chroma 与 Pinecone 后端切换。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from langchain_community.embeddings import OpenAIEmbeddings
from langchain_community.vectorstores import Chroma

from app.core.config import settings
from app.core.logging import get_logger
from app.services.user_key_context import UserKeyContext

logger = get_logger(__name__)


class VectorStoreBackend(ABC):
    """向量存储后端抽象接口。"""

    @abstractmethod
    def as_retriever(self, search_kwargs: dict[str, Any] | None = None) -> Any:
        """返回 LangChain 检索器实例。"""

    @abstractmethod
    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        """写入文本向量。"""

    @abstractmethod
    def delete(self, ids: list[str]) -> None:
        """删除向量。"""

    def persist(self) -> None:
        """持久化（部分后端可为空操作）。"""


class ChromaVectorStoreBackend(VectorStoreBackend):
    """Chroma 本地向量库后端。"""

    def __init__(
        self,
        kb_id: int,
        embeddings: OpenAIEmbeddings,
    ) -> None:
        self.store = Chroma(
            collection_name=f"kb_{kb_id}",
            embedding_function=embeddings,
            persist_directory=settings.chroma_persist_dir,
        )

    def as_retriever(self, search_kwargs: dict[str, Any] | None = None) -> Any:
        return self.store.as_retriever(search_kwargs=search_kwargs or {"k": 10})

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        self.store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def delete(self, ids: list[str]) -> None:
        self.store.delete(ids=ids)

    def persist(self) -> None:
        self.store.persist()


class PineconeVectorStoreBackend(VectorStoreBackend):
    """Pinecone 线上向量库后端。"""

    def __init__(
        self,
        kb_id: int,
        embeddings: OpenAIEmbeddings,
        user_ctx: UserKeyContext,
    ) -> None:
        pinecone_key = user_ctx.get_provider("pinecone")
        if pinecone_key is None or not pinecone_key.api_key:
            raise ValueError("未配置 Pinecone API Key")
        if not settings.pinecone_index_name:
            raise ValueError("缺少 PINECONE_INDEX_NAME 配置")

        try:
            from pinecone import Pinecone
            from langchain_community.vectorstores import Pinecone as PineconeVectorStore
        except Exception as exc:
            raise ValueError(f"Pinecone 依赖不可用: {exc}") from exc

        client = Pinecone(api_key=pinecone_key.api_key)
        index = client.Index(settings.pinecone_index_name)
        self.store = PineconeVectorStore(
            index=index,
            embedding=embeddings,
            text_key="text",
            namespace=f"kb_{kb_id}",
        )

    def as_retriever(self, search_kwargs: dict[str, Any] | None = None) -> Any:
        kwargs = search_kwargs or {"k": 10}
        return self.store.as_retriever(search_kwargs=kwargs)

    def add_texts(
        self,
        texts: list[str],
        metadatas: list[dict[str, Any]],
        ids: list[str],
    ) -> None:
        self.store.add_texts(texts=texts, metadatas=metadatas, ids=ids)

    def delete(self, ids: list[str]) -> None:
        self.store.delete(ids=ids)


def create_vector_store_backend(
    kb_id: int,
    embeddings: OpenAIEmbeddings,
    user_ctx: UserKeyContext,
) -> VectorStoreBackend:
    """按配置创建向量存储后端，Pinecone 不可用时自动降级到 Chroma。"""
    if settings.vector_store == "pinecone":
        try:
            return PineconeVectorStoreBackend(kb_id=kb_id, embeddings=embeddings, user_ctx=user_ctx)
        except Exception as exc:
            logger.warning("Pinecone 初始化失败，已降级到 Chroma kb_id=%s error=%s", kb_id, exc)
    return ChromaVectorStoreBackend(kb_id=kb_id, embeddings=embeddings)
