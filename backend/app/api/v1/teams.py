"""团队空间 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session
from app.core.response import success_response
from app.services.team_service import team_service

router = APIRouter(prefix="/teams", tags=["团队协作"])


class TeamCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: Optional[str] = None


class TeamMemberAdd(BaseModel):
    user_id: int
    role: str = Field(default="viewer")


@router.get("", summary="我的团队列表")
async def list_teams(
    user: Annotated[CurrentUser, Depends()],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    teams = await team_service.list_teams(db, tenant_id, user.id)
    return success_response(
        data=[{"id": t.id, "name": t.name, "description": t.description} for t in teams]
    )


@router.post("", summary="创建团队")
async def create_team(
    body: TeamCreate,
    user: Annotated[CurrentUser, Depends()],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    team = await team_service.create_team(
        db, tenant_id, user, body.name, body.description
    )
    return success_response(data={"id": team.id, "name": team.name})


@router.post("/{team_id}/members", summary="添加团队成员")
async def add_team_member(
    team_id: int,
    body: TeamMemberAdd,
    _: Annotated[CurrentUser, Depends()],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    member = await team_service.add_member(
        db, team_id, tenant_id, body.user_id, body.role
    )
    return success_response(data={"id": member.id, "role": member.role})
