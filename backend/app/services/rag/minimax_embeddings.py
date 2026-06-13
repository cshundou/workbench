"""
MiniMax Embedding 客户端。

MiniMax 使用 texts + type 请求体，与 OpenAI Embeddings 不兼容。
GroupId 仅在账号需要时传入，省略时部分密钥可直接调用。
"""

from __future__ import annotations

from typing import List, Optional

import httpx

from app.core.logging import get_logger

logger = get_logger(__name__)

DEFAULT_MINIMAX_EMBEDDING_URL = "https://api.minimax.chat/v1/embeddings"
DEFAULT_MINIMAX_EMBEDDING_MODEL = "embo-01"


class MiniMaxEmbeddingsClient:
    """MiniMax embo-01 向量化客户端。"""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MINIMAX_EMBEDDING_MODEL,
        group_id: Optional[str] = None,
        endpoint_url: str = DEFAULT_MINIMAX_EMBEDDING_URL,
    ) -> None:
        self.api_key = api_key
        self.model = model
        self.group_id = (group_id or "").strip() or None
        self.endpoint_url = endpoint_url
        # 与 LangChain OpenAIEmbeddings 对齐，便于日志与缓存键识别
        self.model_name = model

    def embed_documents(self, texts: List[str]) -> List[List[float]]:
        """向量化文档块。"""
        return self._embed(texts, embed_type="db")

    def embed_query(self, text: str) -> List[float]:
        """向量化检索问句。"""
        vectors = self._embed([text], embed_type="query")
        return vectors[0]

    def _embed(self, texts: List[str], embed_type: str) -> List[List[float]]:
        payload = {
            "model": self.model,
            "type": embed_type,
            "texts": texts,
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        params: dict[str, str] = {}
        if self.group_id:
            params["GroupId"] = self.group_id

        with httpx.Client(timeout=60.0) as client:
            response = client.post(
                self.endpoint_url,
                params=params or None,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            parsed = response.json()

        base_resp = parsed.get("base_resp") or {}
        status_code = base_resp.get("status_code", 0)
        if status_code != 0:
            status_msg = base_resp.get("status_msg", "unknown error")
            raise ValueError(f"MiniMax Embedding API 错误: {status_msg}")

        vectors = parsed.get("vectors")
        if not vectors:
            raise ValueError("MiniMax Embedding API 未返回向量数据")

        return vectors
