"""Skill 配置、测试与执行日志 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    UserKeyCtx,
    get_current_tenant_id,
    get_db_session,
    get_user_key_context,
    require_permission,
)
from app.core.permissions import AGENT_WRITE
from app.core.response import success_response
from app.models.plugin import SkillExecutionLog
from app.services.plugin.skill_service import skill_service

router = APIRouter(prefix="/skills", tags=["Skill"])


class SkillConfigUpdate(BaseModel):
    """Skill 配置更新。"""

    config: dict[str, Any] = Field(default_factory=dict)
    enabled: Optional[bool] = None


class SkillStatusUpdate(BaseModel):
    """Skill 启用状态。"""

    enabled: bool


class SkillTestRequest(BaseModel):
    """Skill 测试请求。"""

    parameters: dict[str, Any] = Field(default_factory=dict)


@router.get("", summary="Skill 列表")
async def list_skills(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    enabled_only: bool = Query(False),
) -> dict[str, Any]:
    """列出可用 Skill（原生 + MCP + 插件）。"""
    items = await skill_service.list_skills(db, tenant_id, enabled_only=enabled_only)
    return success_response(data=items)


@router.get("/logs/execution", summary="Skill 执行审计日志")
async def list_skill_execution_logs(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    skill_key: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """查询 Skill 执行审计日志。"""
    stmt = select(SkillExecutionLog).where(SkillExecutionLog.tenant_id == tenant_id)
    if skill_key:
        stmt = stmt.where(SkillExecutionLog.skill_key == skill_key)
    stmt = stmt.order_by(SkillExecutionLog.created_at.desc())
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    logs = list((await db.execute(stmt)).scalars().all())
    return success_response(
        data=[
            {
                "id": log.id,
                "skill_key": log.skill_key,
                "source_type": log.source_type,
                "success": log.success,
                "duration_ms": log.duration_ms,
                "error_message": log.error_message,
                "created_at": log.created_at.isoformat(),
            }
            for log in logs
        ]
    )


@router.get("/{skill_key}", summary="Skill 详情")
async def get_skill_detail(
    skill_key: str,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取 Skill 详情与租户配置。"""
    skill = await skill_service.get_skill(db, tenant_id, skill_key)
    config = await skill_service.get_skill_config(db, tenant_id, skill.id)
    data = skill_service._skill_to_dict(skill)
    data["tenant_config"] = config.config if config else {}
    data["tenant_enabled"] = config.is_enabled if config else skill.is_enabled
    return success_response(data=data)


@router.put("/{skill_key}/config", summary="更新 Skill 配置")
async def update_skill_config(
    skill_key: str,
    body: SkillConfigUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新 Skill 参数配置。"""
    data = await skill_service.update_skill_config(
        db, tenant_id, skill_key, body.config, enabled=body.enabled
    )
    await db.commit()
    return success_response(data=data)


@router.put("/{skill_key}/status", summary="启用/禁用 Skill")
async def update_skill_status(
    skill_key: str,
    body: SkillStatusUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """启用或禁用 Skill。"""
    await skill_service.set_skill_enabled(db, tenant_id, skill_key, body.enabled)
    await db.commit()
    return success_response(data={"enabled": body.enabled})


@router.post("/{skill_key}/test", summary="测试 Skill")
async def test_skill(
    skill_key: str,
    body: SkillTestRequest,
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    user_ctx: Annotated[UserKeyCtx, Depends(get_user_key_context)],
) -> dict[str, Any]:
    """在配置页测试 Skill 执行。"""
    result = await skill_service.test_skill(
        db, tenant_id, user, skill_key, body.parameters, user_ctx
    )
    await db.commit()
    return success_response(data=result)
