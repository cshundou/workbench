"""
MCP HTTP 客户端（向后兼容模块）。

新代码请使用 mcp_http_transport.McpHttpTransport 或 mcp_adapter.McpProtocolAdapter。
"""

from app.services.mcp.mcp_http_transport import McpHttpClient, McpHttpTransport

__all__ = ["McpHttpClient", "McpHttpTransport"]
