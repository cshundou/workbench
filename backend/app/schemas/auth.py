"""
认证相关 Pydantic 模式。
"""

from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """登录请求参数。"""

    username: str = Field(..., min_length=1, max_length=50, description="用户名")
    password: str = Field(..., min_length=1, description="密码")


class LoginResponse(BaseModel):
    """登录响应数据。"""

    token: str = Field(..., description="JWT 令牌")
    expires_in: int = Field(..., description="过期时间（秒）")


class RoleBrief(BaseModel):
    """角色简要信息。"""

    id: int
    name: str
    code: str

    model_config = {"from_attributes": True}


class UserMeInfo(BaseModel):
    """当前用户详细信息。"""

    id: int
    username: str
    email: str
    role: Optional[RoleBrief] = None
    permissions: List[str] = Field(default_factory=list)


class UserMeResponse(BaseModel):
    """获取当前用户信息响应。"""

    user: UserMeInfo
    permissions: List[str] = Field(default_factory=list)
