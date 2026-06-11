"""
pytest 全局 fixture：异步事件循环、测试客户端、Redis 模拟。
"""

import asyncio
from collections.abc import AsyncGenerator, Generator
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import create_app


@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """为整个测试会话提供独立事件循环。"""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def app():
    """创建测试用 FastAPI 应用实例。"""
    return create_app()


@pytest.fixture
async def client(app) -> AsyncGenerator[AsyncClient, None]:
    """异步 HTTP 测试客户端。"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def mock_redis() -> MagicMock:
    """模拟 Redis 异步客户端，支持 get/set/delete。"""
    storage: dict[str, str] = {}

    redis_mock = MagicMock()

    async def _get(key: str) -> str | None:
        return storage.get(key)

    async def _set(key: str, value: str, ex: int | None = None) -> bool:
        storage[key] = value
        return True

    async def _delete(key: str) -> int:
        if key in storage:
            del storage[key]
            return 1
        return 0

    redis_mock.get = AsyncMock(side_effect=_get)
    redis_mock.set = AsyncMock(side_effect=_set)
    redis_mock.delete = AsyncMock(side_effect=_delete)
    redis_mock.ping = AsyncMock(return_value=True)
    redis_mock.storage = storage
    return redis_mock


@pytest.fixture
def patch_get_redis(mock_redis: MagicMock):
    """将 get_redis 替换为内存模拟实现。"""
    with patch("app.core.redis.get_redis", AsyncMock(return_value=mock_redis)):
        with patch(
            "app.services.rag.rag_service.get_redis",
            AsyncMock(return_value=mock_redis),
        ):
            yield mock_redis
