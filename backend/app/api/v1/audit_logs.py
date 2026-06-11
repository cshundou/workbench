"""
审计日志 API 路由。
"""

from datetime import datetime
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.permissions import AUDIT_READ
from app.core.response import success_response
from app.services.audit_service import audit_service

router = APIRouter(prefix="/audit-logs", tags=["审计日志"])


@router.get("", summary="获取审计日志列表")
async def list_audit_logs(
    _: Annotated[CurrentUser, Depends(require_permission(AUDIT_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    action: Optional[str] = Query(default=None, description="动作类型"),
    user_id: Optional[int] = Query(default=None, description="用户 ID"),
    resource_type: Optional[str] = Query(default=None, description="资源类型"),
    resource_id: Optional[int] = Query(default=None, description="资源 ID"),
    start_at: Optional[datetime] = Query(default=None, description="开始时间"),
    end_at: Optional[datetime] = Query(default=None, description="结束时间"),
) -> dict[str, Any]:
    """分页查询当前租户的审计日志。"""
    result = await audit_service.list_audit_logs(
        db=db,
        tenant_id=tenant_id,
        page=page,
        page_size=page_size,
        action=action,
        user_id=user_id,
        resource_type=resource_type,
        resource_id=resource_id,
        start_at=start_at,
        end_at=end_at,
    )
    return success_response(data=result.model_dump())
