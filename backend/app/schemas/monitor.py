"""
系统监控相关 Pydantic 模式。
"""

from typing import Any, Optional

from pydantic import BaseModel, Field


class TokenUsageSummary(BaseModel):
    """Token 消耗汇总。"""

    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    record_count: int = 0


class ApiStatsSummary(BaseModel):
    """API 调用汇总。"""

    total_count: int = 0
    error_count: int = 0
    avg_response_ms: float = 0.0


class HealthComponent(BaseModel):
    """单个组件健康状态。"""

    status: str
    message: str = "ok"


class SystemHealthResponse(BaseModel):
    """系统健康检查响应。"""

    status: str
    timestamp: str
    components: dict[str, HealthComponent]


class ErrorLogItem(BaseModel):
    """错误日志条目。"""

    timestamp: str
    method: str
    path: str
    status_code: int
    message: str
    error: Optional[str] = None


class MonitorQueryParams(BaseModel):
    """监控查询公共参数。"""

    start_date: Optional[str] = Field(default=None, description="开始时间 ISO 格式")
    end_date: Optional[str] = Field(default=None, description="结束时间 ISO 格式")
    group_by: str = Field(default="day", description="分组维度: day / user / model")
