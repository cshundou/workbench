"""
任务队列单元测试。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.core.task_queue import (
    close_task_queue,
    enqueue_task,
    get_arq_redis_settings,
)


class TestTaskQueue:
    """ARQ 任务队列封装。"""

    def test_get_arq_redis_settings(self) -> None:
        settings = get_arq_redis_settings()
        assert settings is not None

    @pytest.mark.asyncio
    async def test_enqueue_task_returns_job_id(self) -> None:
        mock_job = MagicMock()
        mock_job.job_id = "job-abc-123"
        mock_queue = AsyncMock()
        mock_queue.enqueue_job = AsyncMock(return_value=mock_job)

        with patch("app.core.task_queue.get_task_queue", AsyncMock(return_value=mock_queue)):
            task_id = await enqueue_task("parse_document_task", 1, 2, 3)
        assert task_id == "job-abc-123"
        mock_queue.enqueue_job.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_enqueue_task_failure_raises(self) -> None:
        mock_queue = AsyncMock()
        mock_queue.enqueue_job = AsyncMock(return_value=None)

        with patch("app.core.task_queue.get_task_queue", AsyncMock(return_value=mock_queue)):
            with pytest.raises(RuntimeError, match="任务入队失败"):
                await enqueue_task("unknown_task")

    @pytest.mark.asyncio
    async def test_close_task_queue(self) -> None:
        mock_queue = AsyncMock()
        import app.core.task_queue as tq

        tq._task_queue = mock_queue
        await close_task_queue()
        mock_queue.aclose.assert_awaited_once()
        assert tq._task_queue is None
