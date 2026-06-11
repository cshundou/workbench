"""
自定义工具管理 API。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.permissions import AGENT_WRITE
from app.core.response import success_response
from app.schemas.custom_tool import (
    CustomToolCreate,
    CustomToolTestRequest,
    CustomToolUpdate,
)
from app.services.custom_tool_service import custom_tool_service

router = APIRouter(prefix="/tools", tags=["自定义工具"])


@router.get("", summary="获取已注册工具列表")
async def list_custom_tools(
    _current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取当前租户全部自定义工具。"""
    items = await custom_tool_service.list_tools(db, tenant_id)
    return success_response(data=[item.model_dump() for item in items])


@router.post("/register", summary="注册自定义工具")
async def register_custom_tool(
    data: CustomToolCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """注册新的自定义 REST 工具。"""
    result = await custom_tool_service.register_tool(db, tenant_id, current_user, data)
    await db.commit()
    return success_response(data=result.model_dump(), message="工具注册成功")


@router.put("/{tool_id}", summary="更新工具配置")
async def update_custom_tool(
    tool_id: int,
    data: CustomToolUpdate,
    _current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新自定义工具配置。"""
    result = await custom_tool_service.update_tool(db, tool_id, tenant_id, data)
    await db.commit()
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{tool_id}", summary="删除工具")
async def delete_custom_tool(
    tool_id: int,
    _current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除自定义工具。"""
    await custom_tool_service.delete_tool(db, tool_id, tenant_id)
    await db.commit()
    return success_response(message="删除成功")


@router.post("/{tool_id}/test", summary="测试工具调用")
async def test_custom_tool(
    tool_id: int,
    data: CustomToolTestRequest,
    _current_user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """测试自定义工具调用是否正常。"""
    result = await custom_tool_service.test_tool(db, tool_id, tenant_id, data)
    return success_response(data=result)
