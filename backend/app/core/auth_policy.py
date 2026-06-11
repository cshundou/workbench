"""
API 访问级别策略：与前端路由 accessLevel 对齐。
"""

import re
from typing import Literal

ApiAccessLevel = Literal["public", "optional", "strict"]

# optional 级别：匿名可访问的只读 GET 接口（仅返回公开资源）
_OPTIONAL_GET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"^/api/v1/knowledge-bases/?$"),
    re.compile(r"^/api/v1/knowledge-bases/\d+$"),
    re.compile(r"^/api/v1/agents/?$"),
    re.compile(r"^/api/v1/agents/\d+$"),
    re.compile(r"^/api/v1/workflows/?$"),
    re.compile(r"^/api/v1/workflows/\d+$"),
    re.compile(r"^/api/v1/monitor/overview$"),
    re.compile(r"^/api/v1/config/auth$"),
]


def get_api_access_level(path: str, method: str) -> ApiAccessLevel:
    """
    判定 API 请求的访问级别。

    Args:
        path: 请求路径。
        method: HTTP 方法。

    Returns:
        public / optional / strict。
    """
    upper_method = method.upper()

    if path == "/api/v1/config/auth" or path.startswith("/api/v1/health"):
        return "public"

    if upper_method == "GET":
        for pattern in _OPTIONAL_GET_PATTERNS:
            if pattern.match(path):
                return "optional"

    return "strict"
