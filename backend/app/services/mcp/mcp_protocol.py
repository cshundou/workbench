"""
MCP（Model Context Protocol）标准协议定义。

严格遵循 MCP 2024-11-05 规范，不引入任何私有扩展。
参考：https://modelcontextprotocol.io/specification/2024-11-05
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

# MCP 协议版本（按规范协商，不做私有扩展）
MCP_PROTOCOL_VERSION = "2024-11-05"
SUPPORTED_PROTOCOL_VERSIONS = ("2024-11-05", "2025-03-26")

# 标准 JSON-RPC 方法名
MCP_METHOD_INITIALIZE = "initialize"
MCP_METHOD_INITIALIZED = "notifications/initialized"
MCP_METHOD_PING = "ping"
MCP_METHOD_TOOLS_LIST = "tools/list"
MCP_METHOD_TOOLS_CALL = "tools/call"
MCP_METHOD_RESOURCES_LIST = "resources/list"
MCP_METHOD_RESOURCES_READ = "resources/read"
MCP_METHOD_RESOURCES_TEMPLATES_LIST = "resources/templates/list"
MCP_METHOD_PROMPTS_LIST = "prompts/list"
MCP_METHOD_PROMPTS_GET = "prompts/get"

JSONRPC_VERSION = "2.0"


class McpTransportType(str, Enum):
    """MCP 传输层类型。"""

    HTTP = "http"
    STDIO = "stdio"


class McpErrorCode(int, Enum):
    """MCP / JSON-RPC 标准错误码。"""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603


@dataclass
class McpJsonRpcError:
    """JSON-RPC 错误对象。"""

    code: int
    message: str
    data: Optional[Any] = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "McpJsonRpcError":
        return cls(
            code=int(payload.get("code", McpErrorCode.INTERNAL_ERROR)),
            message=str(payload.get("message", "Unknown error")),
            data=payload.get("data"),
        )


class McpProtocolError(Exception):
    """MCP 协议层异常。"""

    def __init__(
        self,
        message: str,
        *,
        code: int = McpErrorCode.INTERNAL_ERROR,
        data: Optional[Any] = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.data = data


@dataclass
class McpClientInfo:
    """MCP 客户端信息（initialize 参数）。"""

    name: str = "ai-workbench"
    version: str = "1.0.0"


@dataclass
class McpServerInfo:
    """MCP 服务端信息（initialize 结果）。"""

    name: str = ""
    version: str = ""
    protocol_version: str = MCP_PROTOCOL_VERSION
    capabilities: dict[str, Any] = field(default_factory=dict)


@dataclass
class McpToolDefinition:
    """MCP 工具定义。"""

    name: str
    description: Optional[str] = None
    input_schema: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpToolDefinition":
        return cls(
            name=str(data.get("name", "")),
            description=data.get("description"),
            input_schema=data.get("inputSchema") or {},
        )


@dataclass
class McpResourceDefinition:
    """MCP 资源定义。"""

    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpResourceDefinition":
        return cls(
            uri=str(data.get("uri", "")),
            name=str(data.get("name", "")),
            description=data.get("description"),
            mime_type=data.get("mimeType"),
        )


@dataclass
class McpPromptDefinition:
    """MCP Prompt 定义。"""

    name: str
    description: Optional[str] = None
    arguments: list[dict[str, Any]] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "McpPromptDefinition":
        return cls(
            name=str(data.get("name", "")),
            description=data.get("description"),
            arguments=list(data.get("arguments") or []),
        )


@dataclass
class McpContentBlock:
    """MCP 内容块（tools/call 结果）。"""

    type: str
    text: Optional[str] = None
    data: Optional[str] = None
    mime_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {"type": self.type}
        if self.text is not None:
            payload["text"] = self.text
        if self.data is not None:
            payload["data"] = self.data
        if self.mime_type is not None:
            payload["mimeType"] = self.mime_type
        return payload


@dataclass
class McpCallToolResult:
    """MCP tools/call 标准结果。"""

    content: list[McpContentBlock] = field(default_factory=list)
    is_error: bool = False

    @classmethod
    def from_dict(cls, data: Optional[dict[str, Any]]) -> "McpCallToolResult":
        if not data:
            return cls()
        blocks: list[McpContentBlock] = []
        for item in data.get("content") or []:
            if not isinstance(item, dict):
                continue
            blocks.append(
                McpContentBlock(
                    type=str(item.get("type", "text")),
                    text=item.get("text"),
                    data=item.get("data"),
                    mime_type=item.get("mimeType"),
                )
            )
        return cls(content=blocks, is_error=bool(data.get("isError")))

    def to_text(self) -> str:
        """将内容块合并为纯文本（供 Agent 消费）。"""
        parts: list[str] = []
        for block in self.content:
            if block.type == "text" and block.text:
                parts.append(block.text)
            elif block.type == "image" and block.mime_type:
                parts.append(f"[image:{block.mime_type}]")
            else:
                parts.append(str(block.to_dict()))
        return "\n".join(parts) if parts else ""


def build_jsonrpc_request(method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """构造标准 JSON-RPC 2.0 请求。"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "id": str(uuid.uuid4()),
        "method": method,
        "params": params or {},
    }


def build_jsonrpc_notification(method: str, params: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """构造标准 JSON-RPC 2.0 通知（无 id）。"""
    return {
        "jsonrpc": JSONRPC_VERSION,
        "method": method,
        "params": params or {},
    }


def build_initialize_params(client: Optional[McpClientInfo] = None) -> dict[str, Any]:
    """构造 initialize 请求参数。"""
    info = client or McpClientInfo()
    return {
        "protocolVersion": MCP_PROTOCOL_VERSION,
        "capabilities": {
            "roots": {"listChanged": True},
            "sampling": {},
        },
        "clientInfo": {"name": info.name, "version": info.version},
    }


def parse_jsonrpc_response(payload: dict[str, Any]) -> Any:
    """解析 JSON-RPC 响应，抛出 McpProtocolError。"""
    if "error" in payload and payload["error"]:
        err = McpJsonRpcError.from_dict(payload["error"])
        raise McpProtocolError(err.message, code=err.code, data=err.data)
    return payload.get("result")


def negotiate_protocol_version(server_version: str) -> str:
    """协商 MCP 协议版本。"""
    if server_version in SUPPORTED_PROTOCOL_VERSIONS:
        return server_version
    # 服务端版本更高时回退到平台支持的最新版本
    return MCP_PROTOCOL_VERSION
