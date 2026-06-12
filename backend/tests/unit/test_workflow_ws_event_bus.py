"""工作流 WebSocket 事件总线单元测试。"""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.workflow.ws_event_bus import WorkflowWsEventBus


def test_publish_serializes_message() -> None:
    """发布事件应写入 Redis Pub/Sub 频道。"""
    bus = WorkflowWsEventBus()
    mock_redis = MagicMock()
    bus._publisher = mock_redis

    bus.publish(
        42,
        {"type": "node_status", "node_id": "planner", "status": "running"},
    )

    mock_redis.publish.assert_called_once()
    channel, payload = mock_redis.publish.call_args[0]
    assert channel == "workflow:ws:broadcast"
    data = json.loads(payload)
    assert data["execution_id"] == 42
    assert data["message"]["node_id"] == "planner"


@pytest.mark.asyncio
async def test_subscriber_forwards_to_ws_manager() -> None:
    """订阅循环应将 Redis 消息转发到本地 WebSocket 管理器。"""
    bus = WorkflowWsEventBus()
    ws_manager = AsyncMock()

    async def fake_listen():
        yield {
            "type": "message",
            "data": json.dumps(
                {
                    "execution_id": 7,
                    "message": {"type": "execution_status", "status": "running"},
                }
            ),
        }

    bus._pubsub = MagicMock()
    bus._pubsub.listen = fake_listen

    await bus._listen_loop(ws_manager)

    ws_manager.broadcast.assert_awaited_once_with(
        7, {"type": "execution_status", "status": "running"}
    )
