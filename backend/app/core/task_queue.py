"""
ARQ 任务队列连接管理。
"""

import asyncio
from typing import Any

from arq import create_pool
from arq.connections import ArqRedis, RedisSettings

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_task_queue: ArqRedis | None = None
_task_queue_lock = asyncio.Lock()


def get_arq_redis_settings() -> RedisSettings:
    """构建 ARQ Redis 连接配置。"""
    return RedisSettings.from_dsn(settings.redis_url)


async def get_task_queue() -> ArqRedis:
    """获取 ARQ 队列连接单例。"""
    global _task_queue
    if _task_queue is not None:
        return _task_queue

    async with _task_queue_lock:
        if _task_queue is None:
            _task_queue = await create_pool(get_arq_redis_settings())
            logger.info("ARQ 任务队列连接已初始化")
    return _task_queue


async def enqueue_task(function_name: str, *args: Any, **kwargs: Any) -> str:
    """
    将任务入队，返回任务 ID。

    Args:
        function_name: worker 中注册的任务函数名。
        *args: 位置参数。
        **kwargs: 关键字参数。

    Returns:
        str: ARQ 任务 ID。
    """
    queue = await get_task_queue()
    job = await queue.enqueue_job(function_name, *args, **kwargs)
    if job is None:
        raise RuntimeError(f"任务入队失败: {function_name}")
    logger.info("任务入队成功 function=%s task_id=%s", function_name, job.job_id)
    return job.job_id


async def close_task_queue() -> None:
    """关闭 ARQ 队列连接。"""
    global _task_queue
    if _task_queue is not None:
        await _task_queue.aclose()
        _task_queue = None
        logger.info("ARQ 任务队列连接已关闭")
