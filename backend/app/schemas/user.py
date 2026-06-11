"""
用户相关 Pydantic 模式。
"""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field, field_validator

from app.core.security import validate_password_complexity
from app.schemas.auth import RoleBrief


class UserCreate(BaseModel):
    """创建用户请求。"""

    username: str = Field(..., min_length=1, max_length=50)
    email: EmailStr = Field(..., max_length=100)
    password: str = Field(..., min_length=8, max_length=128)
    role_id: Optional[int] = Field(default=None, description="角色 ID")
    status: int = Field(default=1, ge=0, le=1, description="0:禁用, 1:启用")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: str) -> str:
        """校验密码复杂度。"""
        validate_password_complexity(value)
        return value


class UserUpdate(BaseModel):
    """更新用户请求。"""

    email: Optional[EmailStr] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    role_id: Optional[int] = Field(default=None, description="角色 ID")
    status: Optional[int] = Field(default=None, ge=0, le=1, description="0:禁用, 1:启用")

    @field_validator("password")
    @classmethod
    def validate_password(cls, value: Optional[str]) -> Optional[str]:
        """校验密码复杂度（留空则跳过）。"""
        if value:
            validate_password_complexity(value)
        return value


class UserResponse(BaseModel):
    """用户响应数据。"""

    id: int
    tenant_id: int
    username: str
    email: str
    role_id: Optional[int] = None
    role: Optional[RoleBrief] = None
    status: int
    last_login_at: Optional[datetime] = None
    last_login_ip: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UserListResponse(BaseModel):
    """用户列表分页响应。"""

    items: List[UserResponse]
    total: int
    page: int
    page_size: int


class UserImportResult(BaseModel):
    """用户批量导入结果。"""

    success_count: int
    failed_count: int
    errors: List[str] = Field(default_factory=list)


class UserBatchStatusRequest(BaseModel):
    """批量启用/禁用用户请求。"""

    user_ids: List[int] = Field(default_factory=list, min_length=1)
    status: int = Field(..., ge=0, le=1, description="0:禁用, 1:启用")


class UserBatchStatusResult(BaseModel):
    """批量状态更新结果。"""

    updated_count: int
    skipped_count: int
    status: int
