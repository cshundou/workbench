"""
错误建议 API。
"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.deps import CurrentUser, get_current_tenant_id, require_permission
from app.core.permissions import WF_READ
from app.core.response import success_response
from app.services.error_advisor import error_advisor_service
from app.utils.error_translator import translate_error_message

router = APIRouter(prefix="/errors", tags=["错误建议"])


class ErrorAdviseRequest(BaseModel):
    """错误建议请求。"""

    raw_error: str = Field(..., min_length=1, description="原始错误信息")
    failed_node_id: Optional[str] = None
    workflow_id: Optional[int] = None
    kb_id: Optional[int] = None
    execution_id: Optional[int] = None


@router.post("/advise", summary="获取错误中文说明与修改建议")
async def advise_error(
    body: ErrorAdviseRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
) -> dict[str, Any]:
    """翻译错误并返回规则/LLM 增强建议。"""
    _ = current_user
    _ = tenant_id
    context = {
        "failed_node_id": body.failed_node_id,
        "workflow_id": body.workflow_id,
        "kb_id": body.kb_id,
        "execution_id": body.execution_id,
    }
    facing = translate_error_message(body.raw_error, context=context)
    suggestions = await error_advisor_service.advise(
        body.raw_error,
        context=context,
    )
    return success_response(
        data={
            "user_message": facing.user_message,
            "error_code": facing.error_code,
            "raw_error": facing.raw_error,
            "suggestions": [s.to_dict() for s in suggestions],
            "llm_enabled": settings.error_advisor_enabled,
        }
    )
