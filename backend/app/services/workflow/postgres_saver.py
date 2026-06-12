"""
Postgres 工作流 Checkpoint 持久化（生产级主存储）。
"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Optional

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import settings
from app.models.workflow_checkpoint import WorkflowCheckpoint

logger = logging.getLogger(__name__)


class PostgresSaver(BaseCheckpointSaver):
    """将 LangGraph 检查点持久化到 PostgreSQL。"""

    def __init__(self) -> None:
        super().__init__()

    @property
    def config_specs(self) -> list[Any]:
        from langchain_core.runnables import ConfigurableFieldSpec

        return [
            ConfigurableFieldSpec(
                id="thread_id",
                annotation=str,
                name="Thread ID",
                description=None,
                default="",
                is_shared=True,
            ),
        ]

    @staticmethod
    def _run_async(coro: Any) -> Any:
        """在独立事件循环中执行协程，避免与 ARQ/FastAPI 主循环共享 asyncpg 连接。"""
        import asyncio
        import concurrent.futures

        def _run_in_fresh_loop() -> Any:
            return asyncio.run(coro)

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return _run_in_fresh_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            return pool.submit(_run_in_fresh_loop).result()

    @staticmethod
    @asynccontextmanager
    async def _ephemeral_session() -> AsyncGenerator[AsyncSession, None]:
        """为 checkpoint 读写创建独立引擎，防止跨 event loop 复用连接池。"""
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

    async def _aget(self, thread_id: str) -> Optional[Checkpoint]:
        async with self._ephemeral_session() as db:
            row = (
                await db.execute(
                    select(WorkflowCheckpoint).where(
                        WorkflowCheckpoint.thread_id == thread_id
                    )
                )
            ).scalar_one_or_none()
            if row is None:
                return None
            return row.checkpoint

    async def _aput(self, thread_id: str, checkpoint: Checkpoint) -> None:
        async with self._ephemeral_session() as db:
            stmt = insert(WorkflowCheckpoint).values(
                thread_id=thread_id,
                checkpoint=checkpoint,
                source="langgraph",
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=[WorkflowCheckpoint.thread_id],
                set_={"checkpoint": checkpoint, "source": "langgraph"},
            )
            await db.execute(stmt)
            await db.commit()

    async def _adelete(self, thread_id: str) -> None:
        async with self._ephemeral_session() as db:
            row = (
                await db.execute(
                    select(WorkflowCheckpoint).where(
                        WorkflowCheckpoint.thread_id == thread_id
                    )
                )
            ).scalar_one_or_none()
            if row is not None:
                await db.delete(row)
                await db.commit()

    def get(self, config: RunnableConfig) -> Optional[Checkpoint]:
        thread_id = config["configurable"]["thread_id"]
        return self._run_async(self._aget(thread_id))

    def put(self, config: RunnableConfig, checkpoint: Checkpoint) -> None:
        thread_id = config["configurable"]["thread_id"]
        self._run_async(self._aput(thread_id, checkpoint))

    def delete_checkpoint(self, thread_id: str) -> None:
        """删除指定线程检查点。"""
        self._run_async(self._adelete(thread_id))
        logger.info("已清理 Postgres 检查点 thread_id=%s", thread_id)

    @staticmethod
    def migrate_from_redis_payload(
        thread_id: str, raw_payload: str | bytes
    ) -> bool:
        """将 Redis 历史检查点迁移到 Postgres。"""
        try:
            if isinstance(raw_payload, bytes):
                raw_payload = raw_payload.decode("utf-8")
            checkpoint = json.loads(raw_payload)
            saver = PostgresSaver()
            saver._run_async(saver._aput(thread_id, checkpoint))
            return True
        except Exception as exc:
            logger.warning("Redis→Postgres 检查点迁移失败 thread_id=%s: %s", thread_id, exc)
            return False
