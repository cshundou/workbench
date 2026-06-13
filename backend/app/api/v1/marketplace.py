"""模板市场 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_current_user, get_db_session
from app.core.response import success_response
from app.services.marketplace_service import marketplace_service

router = APIRouter(prefix="/marketplace", tags=["模板市场"])


class ShareTemplateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""
    category: str = "用户分享"
    graph_definition: dict[str, Any]


@router.get("/templates", summary="模板市场列表（50+ 官方）")
async def list_marketplace_templates(
    _: Annotated[CurrentUser, Depends(get_current_user)],
    category: Optional[str] = Query(default=None),
    industry: Optional[str] = Query(default=None),
    keyword: Optional[str] = Query(default=None),
) -> dict[str, Any]:
    items = marketplace_service.list_templates(
        category=category, industry=industry, keyword=keyword
    )
    return success_response(data={"items": items, "total": len(items)})


@router.get("/templates/{template_id}", summary="模板详情")
async def get_marketplace_template(
    template_id: str,
    _: Annotated[CurrentUser, Depends(get_current_user)],
) -> dict[str, Any]:
    tpl = marketplace_service.get_template(template_id)
    return success_response(data=tpl)


@router.post("/templates/share", summary="分享模板到市场")
async def share_template(
    body: ShareTemplateRequest,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    record = await marketplace_service.share_template(
        db,
        tenant_id,
        user,
        body.name,
        body.description,
        body.category,
        body.graph_definition,
    )
    return success_response(data={"id": record.id, "status": record.status})
