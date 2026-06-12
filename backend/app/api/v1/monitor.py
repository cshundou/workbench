"""
系统监控 API 路由（文档 8.7）。
"""

from datetime import datetime, timezone
from typing import Annotated, Any, Optional

from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.permissions import MONITOR_READ
from app.core.response import success_response
from app.services.monitor_service import monitor_service

router = APIRouter(prefix="/monitor", tags=["系统监控"])


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    解析 ISO 格式时间字符串。

    Args:
        value: ISO 时间字符串。

    Returns:
        带时区的 datetime，解析失败返回 None。
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed
    except ValueError:
        return None


@router.get("/token-usage", summary="Token 消耗统计")
async def get_token_usage(
    current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: Optional[str] = Query(default=None, description="开始时间"),
    end_date: Optional[str] = Query(default=None, description="结束时间"),
    user_id: Optional[int] = Query(default=None, description="按用户过滤"),
    model_name: Optional[str] = Query(default=None, description="按模型过滤"),
    group_by: str = Query(default="day", description="分组: day / user / model"),
) -> dict[str, Any]:
    """按用户、模型、时间维度统计 Token 消耗。"""
    if group_by not in {"day", "user", "model"}:
        group_by = "day"

    result = await monitor_service.get_token_usage_stats(
        db=db,
        tenant_id=tenant_id,
        start_date=_parse_datetime(start_date),
        end_date=_parse_datetime(end_date),
        user_id=user_id,
        model_name=model_name,
        group_by=group_by,
    )
    return success_response(data=result)


@router.get("/api-stats", summary="API 调用统计")
async def get_api_stats(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    days: int = Query(default=7, ge=1, le=30, description="统计最近天数"),
) -> dict[str, Any]:
    """查询接口调用量与平均响应时间。"""
    result = await monitor_service.get_api_stats(days=days)
    return success_response(data=result)


@router.get("/workflow-stats", summary="工作流执行统计")
async def get_workflow_stats(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    days: int = Query(default=7, ge=1, le=30, description="统计最近天数"),
) -> dict[str, Any]:
    """查询工作流执行次数、平均耗时与失败率。"""
    result = await monitor_service.get_workflow_stats(days=days)
    return success_response(data=result)


@router.get("/tool-stats", summary="工具调用成功率统计")
async def get_tool_stats(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    days: int = Query(default=7, ge=1, le=30, description="统计最近天数"),
) -> dict[str, Any]:
    """查询各工具调用次数、成功次数与成功率趋势。"""
    result = await monitor_service.get_tool_stats(days=days)
    return success_response(data=result)


@router.get("/error-logs", summary="错误日志查询")
async def get_error_logs(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    page: int = Query(default=1, ge=1, description="页码"),
    page_size: int = Query(default=20, ge=1, le=100, description="每页数量"),
    status_code: Optional[int] = Query(default=None, description="按状态码过滤"),
) -> dict[str, Any]:
    """分页查询系统错误日志。"""
    result = await monitor_service.get_error_logs(
        page=page,
        page_size=page_size,
        status_code=status_code,
    )
    return success_response(data=result)


@router.get("/health", summary="系统健康检查")
async def get_monitor_health() -> dict[str, Any]:
    """
    检查数据库、Redis 等组件健康状态。

    无需认证，供运维探活使用。
    """
    result = await monitor_service.get_system_health()
    return success_response(data=result)


@router.get("/user-activity", summary="用户活跃度统计")
async def get_user_activity(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """查询 DAU/WAU/MAU、活跃用户 Top10 与模块访问占比。"""
    result = await monitor_service.get_user_activity(db)
    return success_response(data=result)


@router.get("/alerts/config", summary="告警配置")
async def get_alert_config(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
) -> dict[str, Any]:
    """查询监控告警阈值与通知渠道配置。"""
    result = await monitor_service.get_alert_config()
    return success_response(data=result)


@router.get("/alerts/history", summary="告警历史")
async def get_alert_history(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    limit: int = Query(default=20, ge=1, le=100, description="返回条数"),
) -> dict[str, Any]:
    """查询最近监控告警记录。"""
    items = await monitor_service.get_alert_history(limit=limit)
    return success_response(data={"items": items, "total": len(items)})


@router.get("/token-usage/export/csv", summary="导出 Token 消耗报表 CSV")
async def export_token_usage_csv(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: Optional[str] = Query(default=None, description="开始时间"),
    end_date: Optional[str] = Query(default=None, description="结束时间"),
    group_by: str = Query(default="day", description="分组: day / user / model"),
) -> Response:
    """导出 Token 消耗统计报表为 CSV。"""
    if group_by not in {"day", "user", "model"}:
        group_by = "day"
    csv_content = await monitor_service.export_token_usage_csv(
        db=db,
        tenant_id=tenant_id,
        start_date=_parse_datetime(start_date),
        end_date=_parse_datetime(end_date),
        group_by=group_by,
    )
    return Response(
        content=csv_content.encode("utf-8-sig"),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="token_usage.csv"'},
    )


@router.get("/token-usage/export/excel", summary="导出 Token 消耗报表 Excel")
async def export_token_usage_excel(
    _current_user: Annotated[CurrentUser, Depends(require_permission(MONITOR_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    start_date: Optional[str] = Query(default=None, description="开始时间"),
    end_date: Optional[str] = Query(default=None, description="结束时间"),
    group_by: str = Query(default="day", description="分组: day / user / model"),
) -> Response:
    """导出 Token 消耗统计报表为 Excel。"""
    if group_by not in {"day", "user", "model"}:
        group_by = "day"
    excel_content = await monitor_service.export_token_usage_excel(
        db=db,
        tenant_id=tenant_id,
        start_date=_parse_datetime(start_date),
        end_date=_parse_datetime(end_date),
        group_by=group_by,
    )
    return Response(
        content=excel_content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="token_usage.xlsx"'},
    )

