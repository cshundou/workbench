"""
审计日志相关 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel


class AuditLogResponse(BaseModel):
    """审计日志响应数据。"""

    id: int
    tenant_id: int
    user_id: Optional[int] = None
    action: str
    resource_type: Optional[str] = None
    resource_id: Optional[int] = None
    detail: Optional[dict[str, Any]] = None
    ip_address: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogListResponse(BaseModel):
    """审计日志列表分页响应。"""

    items: List[AuditLogResponse]
    total: int
    page: int
    page_size: int
