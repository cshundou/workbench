"""
租户相关 Pydantic 模式。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TenantCreate(BaseModel):
    """创建租户请求。"""

    name: str = Field(..., min_length=1, max_length=100, description="租户名称")
    domain: str = Field(..., min_length=1, max_length=100, description="租户域标识")
    status: int = Field(default=1, ge=0, le=1, description="状态：0=禁用，1=启用")
    monthly_token_limit: int = Field(
        default=0,
        ge=0,
        description="月度 Token 配额，0 表示不限制",
    )


class TenantUpdate(BaseModel):
    """更新租户请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    domain: Optional[str] = Field(default=None, min_length=1, max_length=100)
    status: Optional[int] = Field(default=None, ge=0, le=1)
    monthly_token_limit: Optional[int] = Field(
        default=None,
        ge=0,
        description="月度 Token 配额，0 表示不限制",
    )


class TenantResponse(BaseModel):
    """租户响应数据。"""

    id: int
    name: str
    domain: str
    status: int
    monthly_token_limit: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class TenantListResponse(BaseModel):
    """租户列表分页响应。"""

    items: List[TenantResponse]
    total: int
    page: int
    page_size: int
