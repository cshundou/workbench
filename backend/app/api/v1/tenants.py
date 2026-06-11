"""
租户管理 API 路由（超管）。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_db_session, require_super_admin
from app.core.exceptions import NotFoundError
from app.core.response import success_response
from app.schemas.tenant import TenantCreate, TenantUpdate
from app.services.tenant_service import tenant_service

router = APIRouter(prefix="/tenants", tags=["租户管理"])


def _get_client_ip(request: Request) -> str | None:
    """提取客户端 IP。"""
    return request.client.host if request.client else None


@router.get("", summary="获取租户列表")
async def list_tenants(
    _: Annotated[CurrentUser, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
) -> dict[str, Any]:
    """分页查询租户列表。"""
    result = await tenant_service.list_tenants(db, page, page_size)
    return success_response(data=result.model_dump())


@router.post("", summary="创建租户")
async def create_tenant(
    request: Request,
    data: TenantCreate,
    current_user: Annotated[CurrentUser, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建新租户。"""
    result = await tenant_service.create_tenant(
        db=db,
        data=data,
        actor_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/{tenant_id}", summary="获取租户详情")
async def get_tenant(
    tenant_id: int,
    _: Annotated[CurrentUser, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取指定租户详情。"""
    tenant = await tenant_service.get_tenant_by_id(db, tenant_id)
    if tenant is None:
        raise NotFoundError(message="租户不存在")
    return success_response(data=tenant_service._to_response(tenant).model_dump())


@router.put("/{tenant_id}", summary="更新租户")
async def update_tenant(
    tenant_id: int,
    request: Request,
    data: TenantUpdate,
    current_user: Annotated[CurrentUser, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新租户信息。"""
    result = await tenant_service.update_tenant(
        db=db,
        tenant_id=tenant_id,
        data=data,
        actor_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
    return success_response(data=result.model_dump(), message="更新成功")


@router.delete("/{tenant_id}", summary="删除租户")
async def delete_tenant(
    tenant_id: int,
    request: Request,
    current_user: Annotated[CurrentUser, Depends(require_super_admin)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除租户。"""
    await tenant_service.delete_tenant(
        db=db,
        tenant_id=tenant_id,
        actor_user_id=current_user.id,
        ip_address=_get_client_ip(request),
    )
    return success_response(message="删除成功")
