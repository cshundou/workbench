"""
工作流 WebSocket 跨进程事件总线。

ARQ Worker 与 FastAPI 为独立进程，内存中的 WebSocket 连接池无法共享。
通过 Redis Pub/Sub 将 Worker 侧事件转发到 API 进程，再推送给前端连接。
"""

import asyncio
import json
import logging
from typing import Any, Optional

import redis
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_WS_CHANNEL = "workflow:ws:broadcast"


class WorkflowWsEventBus:
    """工作流 WebSocket Redis 事件总线。"""

    def __init__(self) -> None:
        self._publisher = redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._subscriber_redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._listen_task: Optional[asyncio.Task[None]] = None

    def publish(self, execution_id: int, message: dict[str, Any]) -> None:
        """发布 WebSocket 事件（Worker / API 均可调用）。"""
        payload = json.dumps(
            {"execution_id": execution_id, "message": message},
            default=str,
            ensure_ascii=False,
        )
        try:
            self._publisher.publish(_WS_CHANNEL, payload)
        except Exception as exc:
            logger.warning(
                "发布工作流 WS 事件失败 execution_id=%s: %s", execution_id, exc
            )

    async def start_subscriber(self) -> None:
        """在 FastAPI 进程启动 Redis 订阅，将事件转发到本地 WebSocket 连接池。"""
        if self._listen_task is not None:
            return

        from app.services.workflow.ws_manager import workflow_ws_manager

        self._subscriber_redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._pubsub = self._subscriber_redis.pubsub()
        await self._pubsub.subscribe(_WS_CHANNEL)
        self._listen_task = asyncio.create_task(
            self._listen_loop(workflow_ws_manager),
            name="workflow-ws-subscriber",
        )
        logger.info("工作流 WebSocket 事件订阅已启动 channel=%s", _WS_CHANNEL)

    async def stop_subscriber(self) -> None:
        """停止订阅并释放资源。"""
        if self._listen_task is not None:
            self._listen_task.cancel()
            try:
                await self._listen_task
            except asyncio.CancelledError:
                pass
            self._listen_task = None

        if self._pubsub is not None:
            try:
                await self._pubsub.unsubscribe(_WS_CHANNEL)
                await self._pubsub.aclose()
            except Exception as exc:
                logger.warning("关闭 WS PubSub 失败: %s", exc)
            self._pubsub = None

        if self._subscriber_redis is not None:
            try:
                await self._subscriber_redis.aclose()
            except Exception as exc:
                logger.warning("关闭 WS 订阅 Redis 失败: %s", exc)
            self._subscriber_redis = None

        logger.info("工作流 WebSocket 事件订阅已停止")

    async def _listen_loop(self, ws_manager: Any) -> None:
        """消费 Redis 消息并广播到本进程 WebSocket 连接。"""
        if self._pubsub is None:
            return

        try:
            async for raw in self._pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(raw.get("data", "{}"))
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("解析 WS 事件失败: %s", exc)
                    continue

                execution_id = envelope.get("execution_id")
                message = envelope.get("message")
                if not execution_id or not isinstance(message, dict):
                    continue

                await ws_manager.broadcast(int(execution_id), message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("工作流 WS 订阅循环异常: %s", exc)


workflow_ws_event_bus = WorkflowWsEventBus()
