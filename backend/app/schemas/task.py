"""
异步任务相关 Pydantic 模式。
"""

from typing import Any, Optional

from pydantic import BaseModel


class TaskStatusResponse(BaseModel):
    """任务状态响应。"""

    task_id: str
    status: str
    result: Optional[Any] = None
    error: Optional[str] = None
