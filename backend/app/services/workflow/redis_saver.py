"""
Redis 工作流状态持久化。

langgraph 0.0.26 未内置 RedisSaver，此处实现与文档 5.3.2 兼容的 Redis 检查点存储。
"""

import json
import logging
from typing import Any, Optional

import redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint

logger = logging.getLogger(__name__)

_CHECKPOINT_PREFIX = "langgraph:checkpoint:"


class RedisSaver(BaseCheckpointSaver):
    """将 LangGraph 检查点持久化到 Redis。"""

    def __init__(self, redis_client: redis.Redis) -> None:
        super().__init__()
        object.__setattr__(self, "redis", redis_client)

    @property
    def config_specs(self) -> list[Any]:
        from langchain_core.runnables import ConfigurableFieldSpec

        return [
            ConfigurableFieldSpec(
                id="thread_id",
                annotation=str,
                name="Thread ID",
                description=None,
                default="",
                is_shared=True,
            ),
        ]

    def _key(self, thread_id: str) -> str:
        return f"{_CHECKPOINT_PREFIX}{thread_id}"

    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """从 Redis 读取检查点。"""
        thread_id = config["configurable"]["thread_id"]
        raw = self.redis.get(self._key(thread_id))
        if raw is None:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.error("反序列化检查点失败 thread_id=%s: %s", thread_id, exc)
            return None

    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> None:
        """将检查点写入 Redis。"""
        thread_id = config["configurable"]["thread_id"]
        try:
            payload = json.dumps(checkpoint, default=str)
            self.redis.set(self._key(thread_id), payload)
        except (TypeError, ValueError) as exc:
            logger.error("序列化检查点失败 thread_id=%s: %s", thread_id, exc)
            raise

    def delete_checkpoint(self, thread_id: str) -> None:
        """删除指定线程的 Redis 检查点。"""
        try:
            self.redis.delete(self._key(thread_id))
            logger.info("已清理工作流检查点 thread_id=%s", thread_id)
        except Exception as exc:
            logger.warning("清理检查点失败 thread_id=%s: %s", thread_id, exc)
