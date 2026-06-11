"""
API v1 路由聚合模块。
"""

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter

from app.api.v1.auth import router as auth_router
from app.api.v1.config import router as config_router
from app.api.v1.agents import router as agents_router
from app.api.v1.audit_logs import router as audit_logs_router
from app.api.v1.knowledge_bases import router as knowledge_bases_router
from app.api.v1.monitor import router as monitor_router
from app.api.v1.roles import router as roles_router
from app.api.v1.tasks import router as tasks_router
from app.api.v1.tools import router as tools_router
from app.api.v1.tenants import router as tenants_router
from app.api.v1.users import router as users_router
from app.api.v1.user_api_keys import router as user_api_keys_router
from app.api.v1.workflow_ws import router as workflow_ws_router
from app.api.v1.workflows import router as workflows_router
from app.core.config import settings
from app.core.logging import get_logger
from app.core.response import success_response

logger = get_logger(__name__)

api_router = APIRouter()

# 注册业务路由
api_router.include_router(auth_router)
api_router.include_router(config_router)
api_router.include_router(users_router)
api_router.include_router(roles_router)
api_router.include_router(knowledge_bases_router)
api_router.include_router(workflows_router)
api_router.include_router(workflow_ws_router)
api_router.include_router(monitor_router)
api_router.include_router(agents_router)
api_router.include_router(user_api_keys_router)
api_router.include_router(audit_logs_router)
api_router.include_router(tenants_router)
api_router.include_router(tasks_router)
api_router.include_router(tools_router)


@api_router.get("/health", summary="健康检查", tags=["系统"])
async def health_check() -> dict[str, Any]:
    """
    服务健康检查接口。

    用于容器编排与负载均衡探活，无需认证。

    Returns:
        统一格式的健康状态响应。
    """
    logger.debug("健康检查请求")
    return success_response(
        data={
            "status": "healthy",
            "app_name": settings.app_name,
            "environment": settings.app_env,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        message="success",
        code=200,
    )
