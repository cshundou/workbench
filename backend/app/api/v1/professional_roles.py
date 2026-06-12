"""
专业角色库 API 路由。
"""

import logging
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.permissions import WF_READ, WF_WRITE
from app.core.response import success_response
from app.schemas.professional_role import (
    ProfessionalRoleCreate,
    ProfessionalRoleUpdate,
    TeamBuildRequest,
    TeamTemplateCreate,
)
from app.services.workflow.professional_role_service import professional_role_service
from app.services.workflow.team_builder import team_builder
from app.services.workflow.team_template_service import team_template_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/professional-roles", tags=["专业角色库"])


@router.get("", summary="获取专业角色列表")
async def list_professional_roles(
    _: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    category: Optional[str] = Query(default=None, description="角色分类筛选"),
) -> dict[str, Any]:
    """列出系统预设与租户自定义专业角色。"""
    roles = await professional_role_service.list_roles(
        db, tenant_id, category=category
    )
    return success_response(data=[r.model_dump() for r in roles])


@router.get("/{role_id}", summary="获取专业角色详情")
async def get_professional_role(
    role_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取单个专业角色详情。"""
    role = await professional_role_service.get_role(db, role_id, tenant_id)
    return success_response(data=role.model_dump())


@router.post("", summary="创建自定义专业角色")
async def create_professional_role(
    data: ProfessionalRoleCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建租户自定义专业角色。"""
    role = await professional_role_service.create_custom_role(
        db, tenant_id, current_user, data
    )
    await db.commit()
    return success_response(data=role.model_dump(), message="角色创建成功")


@router.put("/{role_id}", summary="更新自定义专业角色")
async def update_professional_role(
    role_id: int,
    data: ProfessionalRoleUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新租户自定义专业角色。"""
    role = await professional_role_service.update_role(db, role_id, tenant_id, data)
    await db.commit()
    return success_response(data=role.model_dump(), message="角色更新成功")


@router.delete("/{role_id}", summary="删除自定义专业角色")
async def delete_professional_role(
    role_id: int,
    _: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除租户自定义专业角色。"""
    await professional_role_service.delete_role(db, role_id, tenant_id)
    await db.commit()
    return success_response(message="角色已删除")


# ---- 团队组建与模板 ----

team_router = APIRouter(prefix="/team", tags=["智能团队"])


@team_router.post("/build", summary="智能组建团队")
async def build_team(
    data: TeamBuildRequest,
    _: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
) -> dict[str, Any]:
    """根据任务描述自动组建动态团队，返回结构化团队配置。"""
    custom = data.team_config.model_dump() if data.team_config else None
    config = team_builder.build(
        data.task,
        template_id=data.template_id,
        custom_config=custom,
    )
    return success_response(data=config)


@team_router.get("/templates", summary="获取团队模板列表")
async def list_team_templates(
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    scenario: Optional[str] = Query(default=None, description="场景筛选"),
) -> dict[str, Any]:
    """获取官方与用户自定义团队模板。"""
    official = team_template_service.list_official_catalog()
    custom = await team_template_service.list_templates(
        db, tenant_id, current_user.id, scenario=scenario
    )
    return success_response(
        data={
            "official": official,
            "custom": [t.model_dump() for t in custom if not t.is_official],
        }
    )


@team_router.post("/templates", summary="保存团队模板")
async def save_team_template(
    data: TeamTemplateCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """保存用户自定义团队模板。"""
    tpl = await team_template_service.create_template(db, tenant_id, current_user, data)
    await db.commit()
    return success_response(data=tpl.model_dump(), message="模板保存成功")


@team_router.delete("/templates/{template_id}", summary="删除团队模板")
async def delete_team_template(
    template_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """删除用户自定义团队模板。"""
    await team_template_service.delete_template(
        db, template_id, tenant_id, current_user.id
    )
    await db.commit()
    return success_response(message="模板已删除")
