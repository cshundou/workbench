"""
统一 API 响应格式模块。

所有接口返回 {"code": int, "message": str, "data": Any} 结构。
"""

from typing import Any, Generic, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class ApiResponse(BaseModel, Generic[T]):
    """统一 API 响应模型。"""

    code: int = Field(default=200, description="业务状态码")
    message: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")


class ErrorResponse(BaseModel):
    """统一错误响应模型。"""

    code: int = Field(description="业务状态码")
    message: str = Field(description="错误消息")
    data: Optional[Any] = Field(default=None, description="响应数据")
    error: Optional[str] = Field(default=None, description="详细错误信息")


def success_response(
    data: Any = None,
    message: str = "success",
    code: int = 200,
) -> dict[str, Any]:
    """
    构造成功响应字典。

    Args:
        data: 响应数据。
        message: 响应消息。
        code: 业务状态码。

    Returns:
        统一格式的成功响应。
    """
    return {"code": code, "message": message, "data": data}


def error_response(
    message: str,
    code: int = 400,
    data: Any = None,
    error: Optional[str] = None,
) -> dict[str, Any]:
    """
    构造错误响应字典。

    Args:
        message: 错误消息。
        code: 业务状态码。
        data: 附加数据。
        error: 详细错误信息。

    Returns:
        统一格式的错误响应。
    """
    response: dict[str, Any] = {"code": code, "message": message, "data": data}
    if error is not None:
        response["error"] = error
    return response
