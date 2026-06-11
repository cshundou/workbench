"""
FastAPI 应用入口。

配置 CORS、中间件、路由与生命周期事件。
"""

from contextlib import asynccontextmanager
import os
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import close_db, init_db
from app.core.exceptions import AppException
from app.core.logging import get_logger, setup_logging
from app.core.middleware import (
    ExceptionHandlerMiddleware,
    JWTAuthMiddleware,
    RequestLoggingMiddleware,
)
from app.core.rate_limit import RateLimitMiddleware
from app.core.redis import close_redis
from app.core.response import error_response
from app.core.task_queue import close_task_queue

# 初始化日志
setup_logging()
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    应用生命周期管理。

    启动时初始化数据库连接，关闭时释放资源。
    """
    logger.info("应用启动: %s [%s]", settings.app_name, settings.app_env)
    if settings.langchain_tracing_v2:
        if settings.langchain_api_key:
            os.environ["LANGCHAIN_TRACING_V2"] = "true"
            os.environ["LANGCHAIN_API_KEY"] = settings.langchain_api_key
            logger.info("LangSmith 链路追踪已启用")
        else:
            logger.warning("LANGCHAIN_TRACING_V2=true 但未配置 LANGCHAIN_API_KEY，已跳过追踪")
    try:
        await init_db()
    except Exception as exc:
        # 开发环境下数据库未就绪时允许启动，便于先验证 API 骨架
        if settings.app_env == "development":
            logger.warning("数据库初始化跳过（开发模式）: %s", exc)
        else:
            logger.error("数据库初始化失败，应用无法启动: %s", exc)
            raise

    yield

    logger.info("应用关闭")
    try:
        await close_redis()
    except Exception as exc:
        logger.error("关闭 Redis 连接失败: %s", exc)
    try:
        await close_task_queue()
    except Exception as exc:
        logger.error("关闭 ARQ 队列连接失败: %s", exc)
    try:
        await close_db()
    except Exception as exc:
        logger.error("关闭数据库连接失败: %s", exc)


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用实例。

    Returns:
        配置完成的 FastAPI 应用。
    """
    app = FastAPI(
        title=settings.app_name,
        description="企业智能协作工作台 API",
        version="1.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # CORS 跨域配置
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # 自定义中间件（后添加的先执行）
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(JWTAuthMiddleware)
    app.add_middleware(ExceptionHandlerMiddleware)

    # 注册 API 路由
    app.include_router(api_router, prefix=settings.api_v1_prefix)

    # Prometheus 指标（可选）
    if settings.prometheus_enabled:
        try:
            from prometheus_fastapi_instrumentator import Instrumentator

            Instrumentator().instrument(app).expose(
                app,
                endpoint="/metrics",
                include_in_schema=False,
            )
            logger.info("Prometheus 指标端点已启用: /metrics")
        except Exception as exc:
            logger.warning("Prometheus 初始化失败: %s", exc)

    # FastAPI 内置异常处理器
    _register_exception_handlers(app)

    return app


def _register_exception_handlers(app: FastAPI) -> None:
    """注册 FastAPI 内置异常的全局处理器。"""

    @app.exception_handler(AppException)
    async def app_exception_handler(request, exc: AppException) -> JSONResponse:
        """处理自定义业务异常。"""
        return JSONResponse(
            status_code=exc.code,
            content=error_response(
                message=exc.message,
                code=exc.code,
                data=exc.data,
                error=exc.error,
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request, exc: StarletteHTTPException
    ) -> JSONResponse:
        """处理 HTTP 异常（404 等）。"""
        return JSONResponse(
            status_code=exc.status_code,
            content=error_response(
                message=str(exc.detail),
                code=exc.status_code,
                data=None,
                error=str(exc.detail),
            ),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request, exc: RequestValidationError
    ) -> JSONResponse:
        """处理请求参数校验异常。"""
        errors = exc.errors()
        error_msg = "; ".join(
            f"{'.'.join(str(loc) for loc in err['loc'])}: {err['msg']}"
            for err in errors
        )
        logger.warning("请求参数校验失败: %s", error_msg)
        return JSONResponse(
            status_code=422,
            content=error_response(
                message="参数错误",
                code=422,
                data=None,
                error=error_msg,
            ),
        )


# 应用实例，供 uvicorn 启动
app = create_app()
