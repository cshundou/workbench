"""
应用配置模块。

通过环境变量加载配置，支持 .env 文件。
"""

from functools import lru_cache
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，字段名与 .env 环境变量对应。"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # 应用基础配置
    app_name: str = Field(default="AI Workbench", description="应用名称")
    app_env: str = Field(default="development", description="运行环境")
    debug: bool = Field(default=False, description="调试模式")
    api_v1_prefix: str = Field(default="/api/v1", description="API v1 路由前缀")

    # 数据库配置
    database_url: str = Field(
        default="postgresql+asyncpg://postgres:postgres@localhost:5432/ai_workbench",
        description="PostgreSQL 异步连接 URL",
    )

    # Redis 配置
    redis_url: str = Field(
        default="redis://localhost:6379/0",
        description="Redis 连接 URL",
    )

    # JWT 认证配置
    jwt_secret_key: str = Field(
        default="change-me-in-production-use-a-strong-secret-key",
        description="JWT 签名密钥",
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT 签名算法")
    jwt_access_token_expire_minutes: int = Field(
        default=1440,
        description="访问令牌过期时间（分钟）",
    )

    # CORS 配置
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="允许跨域的来源列表",
    )

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_dir: str = Field(default="logs", description="日志文件目录")

    # 认证白名单路径（无需 JWT 即可访问）
    auth_whitelist_paths: List[str] = Field(
        default=[
            "/api/v1/health",
            "/api/v1/auth/login",
            "/docs",
            "/redoc",
            "/openapi.json",
        ],
        description="JWT 认证白名单路径",
    )


@lru_cache
def get_settings() -> Settings:
    """
    获取应用配置单例。

    使用 lru_cache 避免重复解析环境变量。
    """
    return Settings()


# 全局配置实例
settings = get_settings()
