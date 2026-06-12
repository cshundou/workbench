"""
工作流执行运行时状态 Redis 存储。

将节点状态与近期日志从进程内存迁移到 Redis，支持多实例与进程重启后恢复。
"""

import json
import logging
from typing import Any, Optional

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

_RUNTIME_PREFIX = "workflow:runtime:"
_RUNTIME_TTL_SECONDS = 60 * 60 * 24 * 7  # 7 天


class WorkflowRuntimeStateStore:
    """工作流执行运行时状态读写。"""

    def __init__(self, redis_url: str | None = None) -> None:
        url = redis_url or settings.redis_url
        self._redis = redis.Redis.from_url(url, decode_responses=True)

    def _key(self, execution_id: int) -> str:
        return f"{_RUNTIME_PREFIX}{execution_id}"

    def get(self, execution_id: int) -> Optional[dict[str, Any]]:
        """读取运行时状态，不存在返回 None。"""
        raw = self._redis.get(self._key(execution_id))
        if not raw:
            return None
        try:
            return json.loads(raw)
        except (json.JSONDecodeError, TypeError) as exc:
            logger.warning("反序列化运行时状态失败 execution_id=%s: %s", execution_id, exc)
            return None

    def save(self, execution_id: int, state: dict[str, Any]) -> None:
        """写入运行时状态并刷新 TTL。"""
        try:
            payload = json.dumps(state, default=str, ensure_ascii=False)
            self._redis.setex(self._key(execution_id), _RUNTIME_TTL_SECONDS, payload)
        except (TypeError, ValueError) as exc:
            logger.warning("序列化运行时状态失败 execution_id=%s: %s", execution_id, exc)

    def delete(self, execution_id: int) -> None:
        """删除运行时状态（终止执行后清理）。"""
        try:
            self._redis.delete(self._key(execution_id))
        except Exception as exc:
            logger.warning("删除运行时状态失败 execution_id=%s: %s", execution_id, exc)

    def merge_update(self, execution_id: int, patch: dict[str, Any]) -> dict[str, Any]:
        """合并更新运行时状态。"""
        current = self.get(execution_id) or {}
        current.update(patch)
        self.save(execution_id, current)
        return current


runtime_state_store = WorkflowRuntimeStateStore()
