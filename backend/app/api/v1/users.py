"""
用户管理 API 路由。
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response
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
from app.schemas.user import UserBatchStatusRequest, UserCreate, UserUpdate
from app.services.user_service import user_service

router = APIRouter(prefix="/users", tags=["用户管理"])


@router.get("", summary="获取用户列表")
async def list_users(
    _: Annotated[CurrentUser, Depends(require_permission(USER_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    keyword: str | None = Query(default=None, description="用户名或邮箱关键词"),
) -> dict[str, Any]:
    """分页查询当前租户下的用户列表。"""
    result = await user_service.list_users(db, tenant_id, page, page_size, keyword=keyword)
    return success_response(data=result.model_dump())


@router.post("", summary="创建用户")
async def create_user(
    current_user: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """在当前租户下创建新用户。"""
    result = await user_service.create_user(db, tenant_id, user_data, current_user.id)
    return success_response(data=result.model_dump(), message="创建成功")


@router.get("/export", summary="导出用户 CSV")
async def export_users(
    _: Annotated[CurrentUser, Depends(require_permission(USER_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> Response:
    """导出当前租户用户列表为 CSV 文件。"""
    csv_content = await user_service.export_users_csv(db, tenant_id)
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="users_export.csv"'},
    )


@router.post("/import", summary="批量导入用户 CSV")
async def import_users(
    current_user: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    file: UploadFile = File(..., description="用户 CSV 文件"),
) -> dict[str, Any]:
    """从 CSV 批量导入用户，表头：username,email,password,role_id,status。"""
    raw = await file.read()
    try:
        csv_content = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        csv_content = raw.decode("gbk", errors="replace")

    result = await user_service.import_users_csv(
        db, tenant_id, csv_content, current_user.id
    )
    return success_response(data=result.model_dump(), message="导入完成")


@router.post("/batch-status", summary="批量更新用户状态")
async def batch_update_user_status(
    data: UserBatchStatusRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """批量启用或禁用用户。"""
    result = await user_service.batch_update_status(
        db=db,
        tenant_id=tenant_id,
        user_ids=data.user_ids,
        status=data.status,
        actor_user_id=current_user.id,
    )
    return success_response(data=result.model_dump(), message="批量更新成功")


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
    current_user: Annotated[CurrentUser, Depends(require_permission(USER_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新指定用户信息。"""
    result = await user_service.update_user(
        db, user_id, tenant_id, user_data, current_user.id
    )
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
