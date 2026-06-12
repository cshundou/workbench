"""AI 效果评估 API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_tenant_id, get_db_session, require_permission
from app.core.permissions import MONITOR_READ
from app.core.response import success_response
from app.services.eval_service import eval_service

router = APIRouter(prefix="/eval", tags=["AI效果评估"])


@router.get("/report", summary="完整评估报告")
async def get_eval_report(
    _: Annotated[object, Depends(require_permission(MONITOR_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    report = await eval_service.get_full_eval_report(db, tenant_id)
    return success_response(data=report)
