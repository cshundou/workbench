"""
自定义工具 Pydantic 模式。
"""

from datetime import datetime
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, HttpUrl


class CustomToolCreate(BaseModel):
    """注册自定义工具请求。"""

    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    parameters_schema: dict[str, Any] = Field(default_factory=dict)
    invoke_url: HttpUrl
    auth_type: Literal["none", "bearer", "api_key"] = "none"
    auth_token: Optional[str] = None


class CustomToolUpdate(BaseModel):
    """更新自定义工具请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    description: Optional[str] = None
    parameters_schema: Optional[dict[str, Any]] = None
    invoke_url: Optional[HttpUrl] = None
    auth_type: Optional[Literal["none", "bearer", "api_key"]] = None
    auth_token: Optional[str] = None
    is_active: Optional[bool] = None


class CustomToolResponse(BaseModel):
    """自定义工具响应。"""

    id: int
    tenant_id: int
    owner_id: int
    name: str
    description: str
    parameters_schema: dict[str, Any]
    invoke_url: str
    auth_type: str
    is_active: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CustomToolTestRequest(BaseModel):
    """测试自定义工具请求。"""

    parameters: dict[str, Any] = Field(default_factory=dict)
