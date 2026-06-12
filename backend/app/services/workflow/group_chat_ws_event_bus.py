"""
群聊 WebSocket 跨进程事件总线。
"""

import asyncio
import json
import logging
from typing import Any, Optional

import redis
import redis.asyncio as aioredis

from app.core.config import settings

logger = logging.getLogger(__name__)

_WS_CHANNEL = "group_chat:ws:broadcast"


class GroupChatWsEventBus:
    """群聊 WebSocket Redis 事件总线。"""

    def __init__(self) -> None:
        self._publisher = redis.Redis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._subscriber_redis: Optional[aioredis.Redis] = None
        self._pubsub: Optional[aioredis.client.PubSub] = None
        self._listen_task: Optional[asyncio.Task[None]] = None

    def publish(self, session_id: int, message: dict[str, Any]) -> None:
        """发布群聊 WebSocket 事件。"""
        payload = json.dumps(
            {"session_id": session_id, "message": message},
            default=str,
            ensure_ascii=False,
        )
        try:
            self._publisher.publish(_WS_CHANNEL, payload)
        except Exception as exc:
            logger.warning("发布群聊 WS 事件失败 session_id=%s: %s", session_id, exc)

    async def start_subscriber(self) -> None:
        """启动 Redis 订阅。"""
        if self._listen_task is not None:
            return

        from app.services.workflow.group_chat_ws_manager import group_chat_ws_manager

        self._subscriber_redis = aioredis.from_url(
            settings.redis_url, decode_responses=True
        )
        self._pubsub = self._subscriber_redis.pubsub()
        await self._pubsub.subscribe(_WS_CHANNEL)
        self._listen_task = asyncio.create_task(
            self._listen_loop(group_chat_ws_manager),
            name="group-chat-ws-subscriber",
        )
        logger.info("群聊 WebSocket 事件订阅已启动 channel=%s", _WS_CHANNEL)

    async def stop_subscriber(self) -> None:
        """停止订阅。"""
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
                logger.warning("关闭群聊 PubSub 失败: %s", exc)
            self._pubsub = None

        if self._subscriber_redis is not None:
            try:
                await self._subscriber_redis.aclose()
            except Exception as exc:
                logger.warning("关闭群聊订阅 Redis 失败: %s", exc)
            self._subscriber_redis = None

    async def _listen_loop(self, ws_manager: Any) -> None:
        """消费 Redis 消息并广播。"""
        if self._pubsub is None:
            return

        try:
            async for raw in self._pubsub.listen():
                if raw.get("type") != "message":
                    continue
                try:
                    envelope = json.loads(raw.get("data", "{}"))
                except (json.JSONDecodeError, TypeError) as exc:
                    logger.warning("解析群聊 WS 事件失败: %s", exc)
                    continue

                session_id = envelope.get("session_id")
                message = envelope.get("message")
                if not session_id or not isinstance(message, dict):
                    continue

                await ws_manager.broadcast_local(int(session_id), message)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.error("群聊 WS 订阅循环异常: %s", exc)


group_chat_ws_event_bus = GroupChatWsEventBus()
