"""
Redis 连接管理模块。

提供异步 Redis 客户端单例，供限流、监控统计等模块复用。
"""

from typing import Optional

import redis.asyncio as aioredis

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """
    获取 Redis 异步客户端单例。

    Returns:
        Redis 异步客户端实例。
    """
    global _redis_client
    if _redis_client is None:
        _redis_client = aioredis.from_url(
            settings.redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis 客户端已初始化")
    return _redis_client


async def close_redis() -> None:
    """关闭 Redis 连接并释放资源。"""
    global _redis_client
    if _redis_client is not None:
        await _redis_client.aclose()
        _redis_client = None
        logger.info("Redis 客户端已关闭")


async def ping_redis() -> bool:
    """
    检测 Redis 连接是否可用。

    Returns:
        连接正常返回 True，否则返回 False。
    """
    try:
        client = await get_redis()
        return bool(await client.ping())
    except Exception as exc:
        logger.warning("Redis 健康检查失败: %s", exc)
        return False
