"""
角色管理 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.exceptions import NotFoundError
from app.core.permissions import ROLE_DELETE, ROLE_READ, ROLE_WRITE
from app.core.response import success_response
from app.models.user import User
from app.schemas.role import RoleCreate, RoleUpdate
from app.services.role_service import role_service

router = APIRouter(prefix="/roles", tags=["角色管理"])


@router.get("", summary="获取角色列表")
async def list_roles(
    _: Annotated[User, Depends(require_permission(ROLE_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询当前租户下的角色列表。"""
    result = await role_service.list_roles(db, tenant_id, page, page_size)
    return success_response(data=result.model_dump())


@router.post("", summary="创建角色")
async def create_role(
    role_data: RoleCreate,
    current_user: Annotated[User, Depends(require_permission(ROLE_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """在当前租户下创建新角色。"""
    result = await role_service.create_role(db, tenant_id, role_data, current_user.id)
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/{role_id}", summary="获取角色详情")
async def get_role(
    role_id: int,
    _: Annotated[User, Depends(require_permission(ROLE_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定角色的详细信息。"""
    role = await role_service.get_role_by_id(db, role_id, tenant_id)
    if role is None:
        raise NotFoundError(message="角色不存在")
    return success_response(data=role_service._to_response(role).model_dump())


@router.put("/{role_id}", summary="更新角色")
async def update_role(
    role_id: int,
    role_data: RoleUpdate,
    current_user: Annotated[User, Depends(require_permission(ROLE_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新指定角色信息。"""
    result = await role_service.update_role(
        db, role_id, tenant_id, role_data, current_user.id
    )
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{role_id}", summary="删除角色")
async def delete_role(
    role_id: int,
    current_user: Annotated[User, Depends(require_permission(ROLE_DELETE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除指定角色。"""
    await role_service.delete_role(db, role_id, tenant_id, current_user.id)
    return success_response(message="删除成功")
