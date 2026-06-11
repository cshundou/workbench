"""
任务状态查询服务单元测试。
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.task_service import TaskService


class TestTaskService:
    """ARQ 任务状态。"""

    @pytest.mark.asyncio
    async def test_get_task_status_complete(self) -> None:
        service = TaskService()
        mock_queue = AsyncMock()
        mock_status = MagicMock()
        mock_status.value = "complete"

        mock_job = MagicMock()
        mock_job.status = AsyncMock(return_value=mock_status)
        mock_job.result = AsyncMock(return_value={"done": True})

        with patch("app.services.task_service.get_task_queue", AsyncMock(return_value=mock_queue)):
            with patch("app.services.task_service.Job", return_value=mock_job):
                result = await service.get_task_status("job-123")
        assert result.task_id == "job-123"
        assert result.status == "complete"
