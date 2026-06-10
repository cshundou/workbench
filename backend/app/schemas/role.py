"""
角色相关 Pydantic 模式。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class RoleCreate(BaseModel):
    """创建角色请求。"""

    name: str = Field(..., min_length=1, max_length=50)
    description: Optional[str] = Field(default=None)
    permissions: List[str] = Field(default_factory=list, description="权限标识列表")


class RoleUpdate(BaseModel):
    """更新角色请求。"""

    name: Optional[str] = Field(default=None, min_length=1, max_length=50)
    description: Optional[str] = None
    permissions: Optional[List[str]] = Field(default=None, description="权限标识列表")


class RoleResponse(BaseModel):
    """角色响应数据。"""

    id: int
    tenant_id: int
    name: str
    description: Optional[str] = None
    permissions: List[str] = Field(default_factory=list)
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class RoleListResponse(BaseModel):
    """角色列表分页响应。"""

    items: List[RoleResponse]
    total: int
    page: int
    page_size: int
