"""
异步数据库连接模块。

基于 SQLAlchemy 2.0 异步引擎与会话管理。
"""

from collections.abc import AsyncGenerator
from typing import Any

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """SQLAlchemy 声明式基类，所有 ORM 模型继承此类。"""

    pass


# 异步数据库引擎
engine: AsyncEngine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    pool_pre_ping=True,
    pool_size=10,
    max_overflow=20,
)

# 异步会话工厂
async_session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    获取数据库会话依赖。

    在请求结束时自动关闭会话，异常时回滚事务。

    Yields:
        AsyncSession: 异步数据库会话。
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception as exc:
            await session.rollback()
            logger.error("数据库会话异常，已回滚: %s", exc)
            raise
        finally:
            await session.close()


async def init_db() -> None:
    """
    初始化数据库连接。

    在应用启动时调用，验证数据库连通性。
    """
    try:
        async with engine.begin() as conn:
            await conn.run_sync(lambda _: None)
        logger.info("数据库连接初始化成功")
    except Exception as exc:
        logger.error("数据库连接初始化失败: %s", exc)
        raise


async def close_db() -> None:
    """关闭数据库连接池，在应用关闭时调用。"""
    try:
        await engine.dispose()
        logger.info("数据库连接池已关闭")
    except Exception as exc:
        logger.error("关闭数据库连接池失败: %s", exc)
        raise
