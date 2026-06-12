"""插件市场与生命周期管理 API。"""

from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import CurrentUser, get_current_tenant_id, get_db_session, require_permission
from app.core.permissions import AGENT_WRITE
from app.core.response import success_response
from app.services.plugin.permissions import CATEGORY_LABELS, PLUGIN_CATEGORIES
from app.services.plugin.plugin_service import plugin_service

router = APIRouter(prefix="/plugins", tags=["插件"])


class PluginInstallRequest(BaseModel):
    """安装插件请求。"""

    plugin_id: str = Field(..., min_length=1)


class PluginConfigUpdate(BaseModel):
    """插件配置更新。"""

    config: dict[str, Any] = Field(default_factory=dict)


class PluginStatusUpdate(BaseModel):
    """启用/禁用插件。"""

    enabled: bool


class PluginReviewCreate(BaseModel):
    """插件评分评论。"""

    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = None


@router.get("/categories", summary="插件分类列表")
async def list_plugin_categories(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
) -> dict[str, Any]:
    """返回插件市场分类。"""
    return success_response(
        data=[
            {"key": key, "label": CATEGORY_LABELS.get(key, key)}
            for key in PLUGIN_CATEGORIES
        ]
    )


@router.get("/marketplace", summary="插件市场列表")
async def list_marketplace(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    category: Optional[str] = Query(None),
    keyword: Optional[str] = Query(None),
    featured_only: bool = Query(False),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
) -> dict[str, Any]:
    """插件市场：分类筛选与搜索。"""
    data = await plugin_service.list_marketplace(
        db,
        tenant_id=tenant_id,
        category=category,
        keyword=keyword,
        featured_only=featured_only,
        page=page,
        page_size=page_size,
    )
    return success_response(data=data)


@router.get("/installed", summary="已安装插件")
async def list_installed_plugins(
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """列出租户已安装插件。"""
    items = await plugin_service.list_installed(db, tenant_id)
    return success_response(data=items)


@router.get("/{plugin_id}", summary="插件详情")
async def get_plugin_detail(
    plugin_id: str,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取插件详情（含 Skill 与评论）。"""
    data = await plugin_service.get_plugin_detail(db, plugin_id)
    return success_response(data=data)


@router.post("/install", summary="安装插件")
async def install_plugin(
    body: PluginInstallRequest,
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """安装插件到当前租户。"""
    installation = await plugin_service.install_plugin(
        db, tenant_id, user, body.plugin_id
    )
    await db.commit()
    return success_response(
        data={
            "installation_id": installation.id,
            "plugin_id": body.plugin_id,
            "status": installation.status,
        },
        message="插件安装成功",
    )


@router.post("/{plugin_id}/uninstall", summary="卸载插件")
async def uninstall_plugin(
    plugin_id: str,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """卸载插件。"""
    await plugin_service.uninstall_plugin(db, tenant_id, plugin_id)
    await db.commit()
    return success_response(message="插件已卸载")


@router.put("/{plugin_id}/status", summary="启用/禁用插件")
async def update_plugin_status(
    plugin_id: str,
    body: PluginStatusUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """启用或禁用已安装插件。"""
    installation = await plugin_service.set_plugin_status(
        db, tenant_id, plugin_id, body.enabled
    )
    await db.commit()
    return success_response(data={"status": installation.status})


@router.put("/{plugin_id}/config", summary="更新插件配置")
async def update_plugin_config(
    plugin_id: str,
    body: PluginConfigUpdate,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """更新插件配置。"""
    installation = await plugin_service.update_plugin_config(
        db, tenant_id, plugin_id, body.config
    )
    await db.commit()
    return success_response(data={"config": installation.config})


@router.post("/{plugin_id}/update", summary="更新已安装插件")
async def update_installed_plugin(
    plugin_id: str,
    _: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """将已安装插件更新到市场最新版本。"""
    installation = await plugin_service.update_installed_plugin(
        db, tenant_id, plugin_id
    )
    await db.commit()
    return success_response(
        data={
            "installed_version": installation.installed_version,
            "status": installation.status,
        },
        message="插件已更新",
    )


@router.post("/{plugin_id}/reviews", summary="提交插件评论")
async def add_plugin_review(
    plugin_id: str,
    body: PluginReviewCreate,
    user: Annotated[CurrentUser, Depends(require_permission(AGENT_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """为插件评分与评论。"""
    review = await plugin_service.add_review(
        db, tenant_id, user, plugin_id, body.rating, body.comment
    )
    await db.commit()
    return success_response(
        data={"rating": review.rating, "comment": review.comment},
        message="评论已提交",
    )
