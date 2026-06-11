"""
异步任务状态查询服务。
"""

from typing import Any

from arq.jobs import Job

from app.core.logging import get_logger
from app.core.task_queue import get_task_queue
from app.schemas.task import TaskStatusResponse

logger = get_logger(__name__)


class TaskService:
    """ARQ 任务状态查询。"""

    async def get_task_status(self, task_id: str) -> TaskStatusResponse:
        """
        查询 ARQ 任务状态。

        Args:
            task_id: 任务 ID。

        Returns:
            TaskStatusResponse: 任务状态信息。
        """
        queue = await get_task_queue()
        job = Job(task_id, redis=queue)
        status = await job.status()
        status_text = status.value if hasattr(status, "value") else str(status)

        result: Any = None
        error: str | None = None

        if status_text in {"complete", "failed"}:
            try:
                result = await job.result(timeout=0)
            except Exception as exc:
                error = str(exc)
                logger.warning("读取任务结果失败 task_id=%s: %s", task_id, exc)

        return TaskStatusResponse(
            task_id=task_id,
            status=status_text,
            result=result if error is None else None,
            error=error,
        )


task_service = TaskService()
