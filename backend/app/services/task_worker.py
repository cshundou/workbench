"""
ARQ Worker 任务函数。
"""

from typing import Any, Optional

from app.core.logging import get_logger
from app.services.rag.rag_service import rag_service
from app.services.workflow.group_chat_service import group_chat_service
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


async def execute_group_chat_task(
    ctx: dict[str, Any],
    session_id: int,
    tenant_id: int,
    user_id: int,
    task: str,
    kb_id: Optional[int],
    thread_id: str,
) -> dict[str, Any]:
    """执行群聊协同任务。"""
    if group_chat_service.is_session_cancelled(session_id):
        logger.info("群聊任务已取消 session_id=%s", session_id)
        return {"session_id": session_id, "status": "cancelled"}
    await group_chat_service.run_group_chat_task(
        session_id=session_id,
        tenant_id=tenant_id,
        user_id=user_id,
        task=task,
        kb_id=kb_id,
        thread_id=thread_id,
    )
    logger.info("群聊协同任务完成 session_id=%s", session_id)
    return {"session_id": session_id, "status": "completed"}


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
    if workflow_service.is_execution_cancelled(execution_id):
        logger.info("工作流任务已取消，跳过执行 execution_id=%s", execution_id)
        return {"execution_id": execution_id, "status": "cancelled"}
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
    approved: bool = True,
    reject_target: Optional[str] = None,
) -> dict[str, Any]:
    """恢复工作流任务（人工批准续跑或驳回打回）。"""
    if workflow_service.is_execution_cancelled(execution_id):
        logger.info("工作流恢复任务已取消 execution_id=%s", execution_id)
        return {"execution_id": execution_id, "status": "cancelled"}
    await workflow_service.run_resume_workflow_task(
        execution_id=execution_id,
        tenant_id=tenant_id,
        input_params=input_params,
        thread_id=thread_id,
        comment=comment,
        approved=approved,
        reject_target=reject_target,
    )
    logger.info("工作流恢复任务完成 execution_id=%s", execution_id)
    return {"execution_id": execution_id, "status": "completed"}
