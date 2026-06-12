"""多端发布 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session
from app.core.response import success_response
from app.services.publish_service import publish_service

router = APIRouter(prefix="/publish", tags=["多端发布"])


class PublishTokenCreate(BaseModel):
    resource_type: str
    resource_id: int
    publish_mode: str = "api"


@router.post("/tokens", summary="创建发布令牌")
async def create_publish_token(
    body: PublishTokenCreate,
    _: Annotated[CurrentUser, Depends()],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    record = await publish_service.create_publish_token(
        db,
        tenant_id,
        body.resource_type,
        body.resource_id,
        body.publish_mode,
    )
    return success_response(
        data={
            "token": record.token,
            "publish_mode": record.publish_mode,
            "embed_url": publish_service.build_embed_url(record.token),
            "api_url": publish_service.build_api_url(record.token),
        }
    )


@router.get("/{token}/info", summary="查询发布令牌信息（公开）")
async def get_publish_info(
    token: str,
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    record = await publish_service.validate_token(db, token)
    return success_response(
        data={
            "resource_type": record.resource_type,
            "resource_id": record.resource_id,
            "publish_mode": record.publish_mode,
        }
    )
