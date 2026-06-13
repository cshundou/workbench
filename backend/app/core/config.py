"""
应用配置模块。

通过环境变量加载配置，支持 .env 文件。
"""

from functools import lru_cache
from typing import List, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """应用全局配置，字段名与 .env 环境变量对应。"""

    model_config = SettingsConfigDict(
        # 支持从 backend/ 或项目根目录加载 .env
        env_file=(".env", "../.env"),
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
    jwt_refresh_token_expire_days: int = Field(
        default=7,
        description="Refresh Token 过期时间（天）",
    )

    # CORS 配置
    cors_origins: List[str] = Field(
        default=["http://localhost:5173", "http://localhost:3000"],
        description="允许跨域的来源列表",
    )

    # 日志配置
    log_level: str = Field(default="INFO", description="日志级别")
    log_dir: str = Field(default="logs", description="日志文件目录")

    # 加密配置（API 密钥 AES-256-GCM 加密存储）
    encryption_secret_key: str = Field(
        default="",
        description="API 密钥加密主密钥（ENCRYPTION_SECRET_KEY）",
    )

    chroma_persist_dir: str = Field(
        default="data/chroma",
        description="Chroma 向量库持久化目录",
    )
    vector_store: Literal["chroma", "pinecone"] = Field(
        default="chroma",
        description="向量存储后端类型（chroma | pinecone）",
    )
    pinecone_index_name: str = Field(
        default="",
        description="Pinecone 索引名称（VECTOR_STORE=pinecone 时必填）",
    )
    upload_dir: str = Field(default="data/uploads", description="文档上传存储目录")
    max_upload_size_mb: int = Field(default=100, description="单文件最大上传大小（MB）")

    # LangSmith 追踪（可选）
    langchain_tracing_v2: bool = Field(
        default=False,
        description="是否启用 LangSmith 链路追踪（LANGCHAIN_TRACING_V2）",
    )
    langchain_api_key: str = Field(
        default="",
        description="LangSmith API Key（LANGCHAIN_API_KEY）",
    )

    # Agent 执行配置
    agent_tool_timeout_seconds: int = Field(
        default=30,
        description="单工具调用超时时间（秒）",
    )
    agent_tool_max_retries: int = Field(
        default=3,
        description="工具调用失败最大重试次数",
    )
    agent_max_context_tokens: int = Field(
        default=8000,
        description="Agent 上下文 Token 上限（超出自动截断）",
    )

    # 安全防护（提示词注入与敏感内容）
    guardrails_enabled: bool = Field(default=True, description="是否启用输入输出安全防护")
    guardrails_moderation_enabled: bool = Field(
        default=False,
        description="是否启用 OpenAI Moderation API 审核",
    )
    openai_api_key_for_moderation: str = Field(
        default="",
        description="内容审核专用 OpenAI API Key（可选）",
    )

    # 密码复杂度策略
    password_min_length: int = Field(default=8, description="密码最小长度")
    password_require_uppercase: bool = Field(default=True, description="密码需包含大写字母")
    password_require_lowercase: bool = Field(default=True, description="密码需包含小写字母")
    password_require_digit: bool = Field(default=True, description="密码需包含数字")
    password_require_special: bool = Field(default=True, description="密码需包含特殊字符")

    # 登录失败锁定
    login_max_attempts: int = Field(default=5, description="登录失败最大尝试次数")
    login_lock_duration_minutes: int = Field(
        default=15,
        description="账号锁定时长（分钟）",
    )

    # 密码重置
    password_reset_token_expire_minutes: int = Field(
        default=30,
        description="密码重置令牌有效期（分钟）",
    )
    password_reset_base_url: str = Field(
        default="http://localhost/reset-password",
        description="密码重置页面基础 URL",
    )

    # 审计日志保留
    audit_log_retention_days: int = Field(
        default=90,
        description="审计日志保留天数",
    )

    # 认证模式：required=全局强制登录；optional=按需登录
    auth_mode: Literal["required", "optional"] = Field(
        default="required",
        description="认证模式（AUTH_MODE）",
    )

    # 接口限流配置（Redis 固定窗口）
    rate_limit_enabled: bool = Field(default=True, description="是否启用接口限流")
    rate_limit_requests: int = Field(default=100, description="限流窗口内最大请求数")
    rate_limit_window_seconds: int = Field(default=60, description="限流窗口时长（秒）")

    # 认证白名单路径（无需 JWT 即可访问）
    auth_whitelist_paths: List[str] = Field(
        default=[
            "/api/v1/health",
            "/api/v1/monitor/health",
            "/api/v1/auth/login",
            "/api/v1/auth/refresh",
            "/api/v1/auth/forgot-password",
            "/api/v1/auth/reset-password",
            "/api/v1/agents/share",
            "/api/v1/config/auth",
            "/metrics",
            "/docs",
            "/redoc",
            "/openapi.json",
        ],
        description="JWT 认证白名单路径",
    )

    # Python REPL 执行模式
    python_repl_mode: Literal["local", "docker"] = Field(
        default="local",
        description="Python REPL 执行模式（local | docker）",
    )
    python_repl_docker_image: str = Field(
        default="python:3.11-slim",
        description="Docker 沙箱镜像",
    )
    python_repl_timeout_seconds: int = Field(
        default=30,
        description="Python REPL 执行超时（秒）",
    )

    # SQL 工具安全配置
    sql_tool_readonly_dsn: str = Field(
        default="",
        description="SQL 工具只读数据库 DSN（为空则使用主库）",
    )
    sql_tool_allowed_tables: str = Field(
        default="",
        description="SQL 工具表白名单（逗号分隔，为空则不限制）",
    )

    # Prometheus 指标
    prometheus_enabled: bool = Field(
        default=False,
        description="是否暴露 /metrics 端点",
    )

    # LangSmith 项目（前端 trace 链接）
    langsmith_project: str = Field(
        default="ai-workbench",
        description="LangSmith 项目名称",
    )
    langsmith_org: str = Field(
        default="",
        description="LangSmith 组织 slug（前端 trace 链接）",
    )

    # 工作流执行配置
    workflow_parallel_max_workers: int = Field(
        default=5,
        description="工作流并行 Agent 最大并发数",
    )
    workflow_execution_timeout_seconds: int = Field(
        default=600,
        description="工作流全局执行超时（秒）",
    )
    workflow_runtime_ttl_seconds: int = Field(
        default=60 * 60 * 24 * 7,
        description="工作流运行时状态 Redis TTL（秒）",
    )
    workflow_max_replan_count: int = Field(
        default=2,
        description="调度中心最大二次规划次数",
    )
    error_advisor_enabled: bool = Field(
        default=False,
        description="是否启用 LLM 错误建议增强（默认仅规则建议）",
    )

    # 监控告警配置
    alert_enabled: bool = Field(default=False, description="是否启用监控告警")
    alert_slow_api_threshold_ms: float = Field(
        default=2000.0,
        description="慢接口告警阈值（毫秒）",
    )
    alert_error_rate_threshold: float = Field(
        default=0.05,
        description="错误率告警阈值（0-1）",
    )
    alert_cooldown_seconds: int = Field(
        default=300,
        description="同类告警冷却时间（秒）",
    )
    alert_email_recipients: str = Field(
        default="",
        description="告警邮件收件人（逗号分隔）",
    )
    alert_smtp_host: str = Field(default="", description="SMTP 服务器地址")
    alert_smtp_port: int = Field(default=587, description="SMTP 端口")
    alert_smtp_user: str = Field(default="", description="SMTP 用户名")
    alert_smtp_password: str = Field(default="", description="SMTP 密码")
    alert_smtp_from: str = Field(default="", description="告警发件人地址")
    alert_dingtalk_webhook: str = Field(
        default="",
        description="钉钉机器人 Webhook URL",
    )
    alert_wecom_webhook: str = Field(
        default="",
        description="企业微信机器人 Webhook URL",
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
