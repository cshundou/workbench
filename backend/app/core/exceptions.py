"""
自定义业务异常模块。
"""

from typing import Any, Optional


class AppException(Exception):
    """应用业务异常基类。"""

    def __init__(
        self,
        message: str = "业务异常",
        code: int = 400,
        data: Any = None,
        error: Optional[str] = None,
    ) -> None:
        self.message = message
        self.code = code
        self.data = data
        self.error = error or message
        super().__init__(self.message)


class AuthenticationError(AppException):
    """认证失败异常。"""

    def __init__(
        self,
        message: str = "未授权访问",
        code: int = 401,
        error: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, code=code, data=None, error=error)


class AuthorizationError(AppException):
    """权限不足异常。"""

    def __init__(
        self,
        message: str = "权限不足",
        code: int = 403,
        error: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, code=code, data=None, error=error)


class NotFoundError(AppException):
    """资源不存在异常。"""

    def __init__(
        self,
        message: str = "资源不存在",
        code: int = 404,
        error: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, code=code, data=None, error=error)


class ConflictError(AppException):
    """资源冲突异常（如唯一约束冲突）。"""

    def __init__(
        self,
        message: str = "资源已存在",
        code: int = 409,
        error: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, code=code, data=None, error=error)


class ValidationError(AppException):
    """业务校验失败异常。"""

    def __init__(
        self,
        message: str = "参数错误",
        code: int = 400,
        error: Optional[str] = None,
    ) -> None:
        super().__init__(message=message, code=code, data=None, error=error)
