"""
跨线程安全执行异步协程（独立事件循环 + 短生命周期 DB 连接）。
"""

from __future__ import annotations

import asyncio
import concurrent.futures
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings


def run_coro_in_fresh_loop(coro: Any) -> Any:
    """
    在全新事件循环中执行协程，避免与 ARQ/FastAPI 主循环共享 asyncpg 连接。

    若当前线程已有运行中的 loop（如 LangGraph executor 线程），则在子线程中新建 loop。
    """
    def _run_in_fresh_loop() -> Any:
        return asyncio.run(coro)

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return _run_in_fresh_loop()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
        return pool.submit(_run_in_fresh_loop).result()


@asynccontextmanager
async def ephemeral_db_session() -> AsyncGenerator[AsyncSession, None]:
    """创建独立引擎的短生命周期数据库会话。"""
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    session_factory = async_sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autocommit=False,
        autoflush=False,
    )
    try:
        async with session_factory() as db:
            yield db
    finally:
        await engine.dispose()
