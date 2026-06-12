"""企业系统连接器 API。"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session, require_permission
from app.core.permissions import AGENT_WRITE
from app.core.response import success_response
from app.services.connector_service import connector_service

router = APIRouter(prefix="/connectors", tags=["企业连接器"])


class ConnectorCreate(BaseModel):
    connector_type: str
    name: str = Field(..., min_length=1, max_length=100)
    config: dict[str, Any] = Field(default_factory=dict)


@router.get("/presets", summary="预置连接器类型")
async def list_connector_presets(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
) -> dict[str, Any]:
    return success_response(data=connector_service.list_presets())


@router.get("", summary="连接器列表")
async def list_connectors(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    items = await connector_service.list_connectors(db, tenant_id)
    return success_response(
        data=[
            {
                "id": c.id,
                "name": c.name,
                "connector_type": c.connector_type,
                "is_active": c.is_active,
            }
            for c in items
        ]
    )


@router.post("", summary="创建连接器")
async def create_connector(
    body: ConnectorCreate,
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    record = await connector_service.create_connector(
        db, tenant_id, user, body.connector_type, body.name, body.config
    )
    return success_response(data={"id": record.id})


@router.post("/{connector_id}/test", summary="测试连接器")
async def test_connector(
    connector_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    connector = await connector_service.get_or_raise(db, connector_id, tenant_id)
    result = await connector_service.test_connector(connector)
    return success_response(data=result)
