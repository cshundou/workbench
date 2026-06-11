"""
ARQ Worker 任务函数。
"""

from typing import Any, Optional

from app.core.logging import get_logger
from app.services.rag.rag_service import rag_service
from app.services.workflow.workflow_service import workflow_service

logger = get_logger(__name__)


async def parse_document_task(
    ctx: dict[str, Any],
    document_id: int,
    user_id: int,
    tenant_id: int,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """解析文档任务。"""
    await rag_service.run_parse_document_task(
        document_id=document_id,
        user_id=user_id,
        tenant_id=tenant_id,
        tags=tags,
    )
    logger.info("文档解析任务完成 document_id=%s", document_id)
    return {"document_id": document_id, "status": "completed"}


async def execute_workflow_task(
    ctx: dict[str, Any],
    execution_id: int,
    workflow_id: int,
    tenant_id: int,
    user_id: int,
    input_params: dict[str, Any],
    thread_id: str,
) -> dict[str, Any]:
    """执行工作流任务。"""
    await workflow_service.run_workflow_task(
        execution_id=execution_id,
        workflow_id=workflow_id,
        tenant_id=tenant_id,
        user_id=user_id,
        input_params=input_params,
        thread_id=thread_id,
    )
    logger.info("工作流执行任务完成 execution_id=%s", execution_id)
    return {"execution_id": execution_id, "status": "completed"}


async def resume_workflow_task(
    ctx: dict[str, Any],
    execution_id: int,
    tenant_id: int,
    input_params: dict[str, Any],
    thread_id: str,
    comment: Optional[str] = None,
) -> dict[str, Any]:
    """恢复工作流任务。"""
    await workflow_service.run_resume_workflow_task(
        execution_id=execution_id,
        tenant_id=tenant_id,
        input_params=input_params,
        thread_id=thread_id,
        comment=comment,
    )
    logger.info("工作流恢复任务完成 execution_id=%s", execution_id)
    return {"execution_id": execution_id, "status": "completed"}
