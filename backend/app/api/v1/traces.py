"""全链路追踪 API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session, require_permission
from app.core.exceptions import NotFoundError
from app.core.permissions import MONITOR_READ
from app.core.response import success_response
from app.services.trace.trace_service import trace_service

router = APIRouter(prefix="/traces", tags=["全链路追踪"])


@router.get("/{trace_id}", summary="获取 Trace 调用树")
async def get_trace_tree(
    trace_id: str,
    _: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    tree = await trace_service.get_trace_tree(db, trace_id, tenant_id)
    if not tree:
        raise NotFoundError(message="Trace 记录不存在或无权访问")
    return success_response(data=tree)
