"""
用户管理 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.exceptions import NotFoundError
from app.core.permissions import USER_DELETE, USER_READ, USER_WRITE
from app.core.response import success_response
from app.schemas.user import UserCreate, UserUpdate
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="获取用户列表")
async def list_users(
    _: Annotated[CurrentUser, Depends(require_permission(USER_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询当前租户下的用户列表。"""
    result = await user_service.list_users(db, tenant_id, page, page_size)
    return success_response(data=result.model_dump())


@router.post("", summary="创建用户")
async def create_user(
    _: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """在当前租户下创建新用户。"""
    result = await user_service.create_user(db, tenant_id, user_data)
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/{user_id}", summary="获取用户详情")
async def get_user(
    user_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(USER_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定用户的详细信息。"""
    user = await user_service.get_user_by_id(db, user_id, tenant_id)
    if user is None:
        raise NotFoundError(message="用户不存在")
    return success_response(data=user_service._to_response(user).model_dump())


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新指定用户信息。"""
    result = await user_service.update_user(db, user_id, tenant_id, user_data)
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{user_id}", summary="删除用户")
async def delete_user(
    user_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(USER_DELETE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除指定用户。"""
    await user_service.delete_user(db, user_id, tenant_id, current_user.id)
    return success_response(message="删除成功")
