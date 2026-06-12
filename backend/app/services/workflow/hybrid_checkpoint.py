"""
混合 Checkpoint：Postgres 主存储 + Redis 二级缓存。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import redis
from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint

from app.services.workflow.postgres_saver import PostgresSaver
from app.services.workflow.redis_saver import RedisSaver, _CHECKPOINT_PREFIX

logger = logging.getLogger(__name__)

_CACHE_TTL_SECONDS = 3600


class HybridCheckpointSaver(BaseCheckpointSaver):
    """Postgres 持久化 + Redis 读缓存。"""

    def __init__(self, redis_client: redis.Redis) -> None:
        super().__init__()
        object.__setattr__(self, "_redis_saver", RedisSaver(redis_client))
        object.__setattr__(self, "_postgres", PostgresSaver())
        object.__setattr__(self, "_redis_client", redis_client)

    @property
    def config_specs(self) -> list[Any]:
        return self._postgres.config_specs

    def _cache_key(self, thread_id: str) -> str:
        return f"{_CHECKPOINT_PREFIX}{thread_id}"

    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        thread_id = config["configurable"]["thread_id"]
        cached = self._redis_saver.get(config)
        if cached is not None:
            return cached

        pg_checkpoint = self._postgres.get(config)
        if pg_checkpoint is not None:
            try:
                payload = json.dumps(pg_checkpoint, default=str)
                self._redis_client.setex(
                    self._cache_key(thread_id), _CACHE_TTL_SECONDS, payload
                )
            except Exception as exc:
                logger.debug("回填 Redis 缓存失败 thread_id=%s: %s", thread_id, exc)
            return pg_checkpoint

        # 兼容：从旧 Redis 主存迁移
        raw = self._redis_client.get(self._cache_key(thread_id))
        if raw and PostgresSaver.migrate_from_redis_payload(thread_id, raw):
            return self._postgres.get(config)
        return None

    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> None:
        self._postgres.put(config, checkpoint)
        try:
            self._redis_saver.put(config, checkpoint)
            thread_id = config["configurable"]["thread_id"]
            self._redis_client.expire(self._cache_key(thread_id), _CACHE_TTL_SECONDS)
        except Exception as exc:
            logger.warning("写入 Redis 缓存失败: %s", exc)

    def delete_checkpoint(self, thread_id: str) -> None:
        """同时清理 Postgres 与 Redis。"""
        self._postgres.delete_checkpoint(thread_id)
        self._redis_saver.delete_checkpoint(thread_id)


def create_checkpointer(redis_client: redis.Redis) -> HybridCheckpointSaver:
    """创建混合检查点存储。"""
    return HybridCheckpointSaver(redis_client)
