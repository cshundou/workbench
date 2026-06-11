"""
异步任务 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from app.core.deps import CurrentUser, require_any_permission
from app.core.permissions import KB_READ, TASK_READ, WF_READ
from app.core.response import success_response
from app.services.task_service import task_service

router = APIRouter(prefix="/tasks", tags=["异步任务"])


@router.get("/{task_id}", summary="获取异步任务状态")
async def get_task_status(
    task_id: str,
    _: Annotated[CurrentUser, Depends(require_any_permission(TASK_READ, KB_READ, WF_READ))],
) -> dict[str, Any]:
    """查询异步任务状态。"""
    result = await task_service.get_task_status(task_id)
    return success_response(data=result.model_dump())
