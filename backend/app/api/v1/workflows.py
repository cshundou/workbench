"""
工作流管理 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Body, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    UserKeyCtx,
    get_current_tenant_id,
    get_db_session,
    get_user_key_context,
    require_permission,
)
from app.core.exceptions import ApiKeyMissingError
from app.core.permissions import WF_DELETE, WF_READ, WF_WRITE
from app.core.response import success_response
from app.schemas.workflow import (
    GraphDefinition,
    GraphValidateRequest,
    HumanInterventionRequest,
    WorkflowCreate,
    WorkflowExecuteRequest,
    WorkflowUpdate,
)
from app.services.workflow.workflow_service import workflow_service

router = APIRouter(prefix="/workflows", tags=["工作流管理"])


@router.get("", summary="获取工作流列表")
async def list_workflows(
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询工作流模板列表。"""
    result = await workflow_service.list_workflows(
        db, tenant_id, current_user, page, page_size
    )
    return success_response(data=result.model_dump())


@router.post("", summary="创建工作流")
async def create_workflow(
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    data: WorkflowCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建新的工作流模板。"""
    result = await workflow_service.create_workflow(
        db, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/executions/{execution_id}", summary="获取执行状态")
async def get_execution_status(
    execution_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取工作流执行状态、节点状态与执行日志。"""
    result = await workflow_service.get_execution_status(
        db, execution_id, tenant_id
    )
    return success_response(data=result.model_dump())


@router.post(
    "/executions/{execution_id}/cancel",
    summary="终止工作流执行",
)
async def cancel_workflow_execution(
    execution_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """终止正在执行的工作流。"""
    result = await workflow_service.cancel_execution(
        db, execution_id, tenant_id, current_user
    )
    return success_response(data=result.model_dump(), message="工作流已终止")


@router.post(
    "/executions/{execution_id}/intervene",
    summary="人工介入确认",
)
async def human_intervention(
    execution_id: int,
    data: HumanInterventionRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """人工介入：批准或拒绝继续执行工作流。"""
    result = await workflow_service.handle_human_intervention(
        db, execution_id, tenant_id, data
    )
    return success_response(data=result.model_dump(), message="操作成功")


@router.get("/{workflow_id}", summary="获取工作流详情")
async def get_workflow(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定工作流详情。"""
    result = await workflow_service.get_workflow(
        db, workflow_id, tenant_id, current_user
    )
    return success_response(data=result.model_dump())


@router.put("/{workflow_id}", summary="更新工作流")
async def update_workflow(
    workflow_id: int,
    data: WorkflowUpdate,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新工作流模板。"""
    result = await workflow_service.update_workflow(
        db, workflow_id, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{workflow_id}", summary="删除工作流")
async def delete_workflow(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_DELETE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除工作流模板。"""
    await workflow_service.delete_workflow(
        db, workflow_id, tenant_id, current_user
    )
    return success_response(message="删除成功")


@router.post("/{workflow_id}/publish", summary="发布工作流")
async def publish_workflow(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    change_note: str | None = Body(default=None, embed=True),
) -> dict[str, Any]:
    """将草稿工作流发布为可执行模板并创建新版本。"""
    result = await workflow_service.publish_workflow(
        db, workflow_id, tenant_id, current_user, change_note=change_note
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="发布成功")


@router.get("/{workflow_id}/versions", summary="获取版本历史")
async def list_workflow_versions(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """查询工作流全部历史版本。"""
    items = await workflow_service.list_workflow_versions(db, workflow_id, tenant_id)
    return success_response(data=items)


@router.post("/{workflow_id}/versions/{version_id}/rollback", summary="回滚版本")
async def rollback_workflow_version(
    workflow_id: int,
    version_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    change_note: str | None = Body(default=None, embed=True),
) -> dict[str, Any]:
    """回滚到指定历史版本（生成新版本）。"""
    result = await workflow_service.rollback_workflow_version(
        db, workflow_id, version_id, tenant_id, current_user, change_note=change_note
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="回滚成功")


@router.get(
    "/executions/{execution_id}/logs/export",
    summary="导出执行日志",
)
async def export_execution_logs(
    execution_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    node_id: str | None = Query(default=None, description="仅导出指定节点日志"),
) -> dict[str, Any]:
    """导出工作流执行日志 JSON。"""
    data = await workflow_service.export_execution_logs(
        db, execution_id, tenant_id, node_id=node_id
    )
    return success_response(data=data)


@router.post("/{workflow_id}/execute", summary="执行工作流")
async def execute_workflow(
    workflow_id: int,
    data: WorkflowExecuteRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> dict[str, Any]:
    """手动执行工作流并传入任务参数。"""
    if not user_ctx.has_llm_key:
        raise ApiKeyMissingError(
            provider="llm",
            message="请先在「设置 > API 密钥管理」中配置至少一个大模型 API 密钥后再执行工作流",
        )
    result = await workflow_service.execute_workflow(
        db, workflow_id, tenant_id, current_user, data
    )
    return success_response(data=result.model_dump(), message="工作流已启动")


@router.post("/{workflow_id}/validate-graph", summary="校验工作流图定义")
async def validate_workflow_graph(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    data: GraphValidateRequest | None = None,
) -> dict[str, Any]:
    """校验 graph_definition 合法性，不传 body 则校验库内定义。"""
    await workflow_service.get_workflow(db, workflow_id, tenant_id, current_user)
    if data and data.graph_definition:
        definition = data.graph_definition.model_dump()
    else:
        workflow = await workflow_service.get_workflow(
            db, workflow_id, tenant_id, current_user
        )
        definition = workflow.graph_definition
    result = workflow_service.validate_graph_definition(definition)
    return success_response(data=result)


@router.get(
    "/{workflow_id}/executions/{execution_id}/replay",
    summary="获取重跑参数",
)
async def get_execution_replay(
    workflow_id: int,
    execution_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取历史执行的 input_params 与图定义快照，供重跑使用。"""
    result = await workflow_service.get_replay_params(
        db, workflow_id, execution_id, tenant_id
    )
    return success_response(data=result)


@router.get("/{workflow_id}/executions", summary="获取执行历史")
async def list_executions(
    workflow_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> dict[str, Any]:
    """查询工作流执行历史记录。"""
    result = await workflow_service.list_executions(
        db, workflow_id, tenant_id, current_user, page, page_size
    )
    return success_response(data=result.model_dump())
