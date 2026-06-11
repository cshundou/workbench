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

    token: str = Field(..., description="JWT 访问令牌")
    refresh_token: str = Field(..., description="JWT 刷新令牌")
    expires_in: int = Field(..., description="访问令牌过期时间（秒）")


class RefreshTokenRequest(BaseModel):
    """刷新令牌请求。"""

    refresh_token: str = Field(..., min_length=1, description="Refresh Token")


class RefreshTokenResponse(BaseModel):
    """刷新令牌响应。"""

    token: str = Field(..., description="新的访问令牌")
    expires_in: int = Field(..., description="过期时间（秒）")


class LogoutRequest(BaseModel):
    """登出请求（可选携带 refresh_token 以加入黑名单）。"""

    refresh_token: Optional[str] = Field(default=None, description="Refresh Token")


class ForgotPasswordRequest(BaseModel):
    """忘记密码请求。"""

    email: EmailStr = Field(..., description="注册邮箱")


class ResetPasswordRequest(BaseModel):
    """重置密码请求。"""

    token: str = Field(..., min_length=32, description="重置令牌")
    new_password: str = Field(..., min_length=8, max_length=128, description="新密码")


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
