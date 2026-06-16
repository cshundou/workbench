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
from app.services.workflow.task_mode_resolver import infer_execution_mode, resolve_task_tool_names
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


def _build_role_map(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    """按 role_id 构建角色映射，便于团队成员远程加载覆盖。"""
    return {str(row.get("role_id", "")): row for row in rows if row.get("role_id")}


def _merge_member_with_role(member: dict[str, Any], role_map: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """将团队成员信息与数据库角色库信息合并。"""
    merged = dict(member)
    role_id = str(member.get("role_id") or member.get("role") or "")
    role = role_map.get(role_id)
    if not role:
        return merged
    merged["name"] = role.get("name") or merged.get("name", role_id)
    merged["avatar"] = role.get("avatar") or merged.get("avatar", "🤖")
    merged["responsibility"] = role.get("responsibility", merged.get("responsibility", ""))
    merged["tools"] = role.get("tools", merged.get("tools", []))
    merged["system_prompt"] = role.get("system_prompt", merged.get("system_prompt", ""))
    merged["color"] = role.get("color", merged.get("color", "#1677FF"))
    if merged.get("execution_mode") is None:
        merged["execution_mode"] = infer_execution_mode(merged)
    if merged.get("task_tools") is None:
        merged["task_tools"] = (
            ["browser", "terminal"] if merged["execution_mode"] == "task" else []
        )
    return merged


@team_router.post("/build", summary="智能组建团队")
async def build_team(
    data: TeamBuildRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """根据任务描述自动组建动态团队，返回结构化团队配置。"""
    role_rows = await professional_role_service.list_roles(db, tenant_id)
    role_map = _build_role_map([row.model_dump() for row in role_rows])

    custom = data.team_config.model_dump() if data.team_config else None
    template_id = data.template_id
    template_numeric_id: Optional[int] = None
    if template_id:
        try:
            template_numeric_id = int(template_id)
        except ValueError:
            template_numeric_id = None

    if template_numeric_id is not None:
        tpl = await team_template_service.get_template(db, template_numeric_id, tenant_id)
        team_config = dict(tpl.team_config or {})
        team_config["template_id"] = str(tpl.id)
        team_config.setdefault("task_description", data.task)
        members = [
            _merge_member_with_role(dict(member), role_map)
            for member in team_config.get("members", [])
        ]
        team_config["members"] = members
        team_config["team_size"] = len(members)
        return success_response(data=team_config)

    config = team_builder.build(
        data.task,
        template_id=template_id,
        custom_config=custom,
    )
    config["members"] = [
        _merge_member_with_role(dict(member), role_map) for member in config.get("members", [])
    ]
    config["team_size"] = len(config["members"])
    config["owner_id"] = current_user.id
    return success_response(data=config)


@team_router.get("/templates", summary="获取团队模板列表")
async def list_team_templates(
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    scenario: Optional[str] = Query(default=None, description="场景筛选"),
) -> dict[str, Any]:
    """获取官方与用户自定义团队模板。"""
    templates = await team_template_service.list_templates(
        db, tenant_id, current_user.id, scenario=scenario
    )
    official = [t.model_dump() for t in templates if t.is_official]
    custom = [t.model_dump() for t in templates if not t.is_official]
    return success_response(
        data={
            "official": official,
            "custom": custom,
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
