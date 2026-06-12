"""
MCP 协议适配器。

统一 HTTP / stdio 传输，暴露标准 MCP 能力（tools / resources / prompts），
供 Skill 执行引擎与 Agent 工具层调用。
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Protocol, Union

from app.models.mcp_server import McpServer
from app.services.mcp.mcp_http_transport import McpHttpTransport
from app.services.mcp.mcp_protocol import (
    MCP_METHOD_PING,
    MCP_METHOD_PROMPTS_GET,
    MCP_METHOD_PROMPTS_LIST,
    MCP_METHOD_RESOURCES_LIST,
    MCP_METHOD_RESOURCES_READ,
    MCP_METHOD_RESOURCES_TEMPLATES_LIST,
    MCP_METHOD_TOOLS_CALL,
    MCP_METHOD_TOOLS_LIST,
    McpCallToolResult,
    McpPromptDefinition,
    McpProtocolError,
    McpResourceDefinition,
    McpServerInfo,
    McpToolDefinition,
    McpTransportType,
)
from app.services.mcp.mcp_stdio_transport import McpStdioTransport

logger = logging.getLogger(__name__)


class McpTransport(Protocol):
    """MCP 传输层协议。"""

    async def initialize(self) -> dict[str, Any]: ...
    async def request(self, method: str, params: Optional[dict[str, Any]] = None) -> Any: ...
    async def close(self) -> None: ...


TransportClient = Union[McpHttpTransport, McpStdioTransport]


class McpSession:
    """MCP 会话上下文。"""

    def __init__(
        self,
        server_id: int,
        transport: TransportClient,
        server_info: McpServerInfo,
    ) -> None:
        self.server_id = server_id
        self.transport = transport
        self.server_info = server_info


class McpProtocolAdapter:
    """
    MCP 协议适配器。

    严格遵循 MCP 标准，兼容所有标准 MCP 工具 / 资源 / Prompt，
    不添加任何私有协议扩展。
    """

    async def connect(self, server: McpServer) -> McpSession:
        """连接 MCP 服务器并完成 initialize 握手。"""
        transport = self._create_transport(server)
        try:
            init_result = await transport.initialize()
        except Exception as exc:
            await transport.close()
            logger.exception("MCP 连接失败 server_id=%s: %s", server.id, exc)
            raise

        server_info_raw = init_result.get("serverInfo") or {}
        server_info = McpServerInfo(
            name=str(server_info_raw.get("name", server.name)),
            version=str(server_info_raw.get("version", "")),
            protocol_version=str(
                init_result.get("protocolVersion") or transport.protocol_version or ""
            ),
            capabilities=dict(init_result.get("capabilities") or {}),
        )
        logger.info(
            "MCP 适配器已连接 server_id=%s name=%s tools_cap=%s",
            server.id,
            server_info.name,
            "tools" in server_info.capabilities,
        )
        return McpSession(server.id, transport, server_info)

    async def disconnect(self, session: McpSession) -> None:
        """关闭 MCP 会话。"""
        try:
            await session.transport.close()
        except Exception as exc:
            logger.warning("MCP 会话关闭异常 server_id=%s: %s", session.server_id, exc)

    async def ping(self, session: McpSession) -> bool:
        """MCP ping 探活。"""
        try:
            await session.transport.request(MCP_METHOD_PING, {})
            return True
        except McpProtocolError as exc:
            if exc.code == -32601:
                # 部分 MCP 服务未实现 ping，视为存活
                return True
            logger.warning("MCP ping 失败 server_id=%s: %s", session.server_id, exc)
            return False

    async def list_tools(self, session: McpSession) -> list[McpToolDefinition]:
        """tools/list — 获取全部 MCP 工具。"""
        result = await session.transport.request(MCP_METHOD_TOOLS_LIST, {})
        tools_raw = (result or {}).get("tools", []) if isinstance(result, dict) else []
        tools = [
            McpToolDefinition.from_dict(item)
            for item in tools_raw
            if isinstance(item, dict) and item.get("name")
        ]
        logger.debug("MCP tools/list server_id=%s count=%s", session.server_id, len(tools))
        return tools

    async def call_tool(
        self,
        session: McpSession,
        name: str,
        arguments: dict[str, Any],
    ) -> McpCallToolResult:
        """tools/call — 调用 MCP 工具。"""
        logger.info(
            "MCP tools/call server_id=%s tool=%s",
            session.server_id,
            name,
        )
        result = await session.transport.request(
            MCP_METHOD_TOOLS_CALL,
            {"name": name, "arguments": arguments},
        )
        call_result = McpCallToolResult.from_dict(result if isinstance(result, dict) else None)
        if call_result.is_error:
            raise McpProtocolError(
                call_result.to_text() or f"MCP 工具 {name} 执行失败",
                code=-32000,
            )
        return call_result

    async def list_resources(self, session: McpSession) -> list[McpResourceDefinition]:
        """resources/list — 获取 MCP 资源列表。"""
        try:
            result = await session.transport.request(MCP_METHOD_RESOURCES_LIST, {})
        except McpProtocolError as exc:
            if exc.code == -32601:
                return []
            raise
        resources_raw = (result or {}).get("resources", []) if isinstance(result, dict) else []
        return [
            McpResourceDefinition.from_dict(item)
            for item in resources_raw
            if isinstance(item, dict) and item.get("uri")
        ]

    async def list_resource_templates(self, session: McpSession) -> list[dict[str, Any]]:
        """resources/templates/list — 获取资源模板。"""
        try:
            result = await session.transport.request(
                MCP_METHOD_RESOURCES_TEMPLATES_LIST, {}
            )
        except McpProtocolError as exc:
            if exc.code == -32601:
                return []
            raise
        templates = (result or {}).get("resourceTemplates", []) if isinstance(result, dict) else []
        return [t for t in templates if isinstance(t, dict)]

    async def read_resource(self, session: McpSession, uri: str) -> dict[str, Any]:
        """resources/read — 读取 MCP 资源。"""
        result = await session.transport.request(
            MCP_METHOD_RESOURCES_READ,
            {"uri": uri},
        )
        return result if isinstance(result, dict) else {"contents": []}

    async def list_prompts(self, session: McpSession) -> list[McpPromptDefinition]:
        """prompts/list — 获取 MCP Prompt 列表。"""
        try:
            result = await session.transport.request(MCP_METHOD_PROMPTS_LIST, {})
        except McpProtocolError as exc:
            if exc.code == -32601:
                return []
            raise
        prompts_raw = (result or {}).get("prompts", []) if isinstance(result, dict) else []
        return [
            McpPromptDefinition.from_dict(item)
            for item in prompts_raw
            if isinstance(item, dict) and item.get("name")
        ]

    async def get_prompt(
        self,
        session: McpSession,
        name: str,
        arguments: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """prompts/get — 获取 MCP Prompt 内容。"""
        params: dict[str, Any] = {"name": name}
        if arguments:
            params["arguments"] = arguments
        result = await session.transport.request(MCP_METHOD_PROMPTS_GET, params)
        return result if isinstance(result, dict) else {}

    def _create_transport(self, server: McpServer) -> TransportClient:
        """根据服务器配置创建传输层。"""
        transport_type = (server.transport or "http").lower()
        config = server.config or {}

        if transport_type == McpTransportType.STDIO.value:
            command = config.get("command") or server.endpoint
            if not command:
                raise McpProtocolError("stdio 传输需要 config.command 或 endpoint 作为命令")
            args = config.get("args") or []
            if isinstance(args, str):
                args = [args]
            return McpStdioTransport(
                command=str(command),
                args=[str(a) for a in args],
                env=config.get("env"),
                cwd=config.get("cwd"),
                timeout=float(config.get("timeout", 60)),
            )

        headers: dict[str, str] = {}
        auth_token = config.get("auth_token")
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"
        extra_headers = config.get("headers") or {}
        if isinstance(extra_headers, dict):
            headers.update({str(k): str(v) for k, v in extra_headers.items()})

        return McpHttpTransport(
            server.endpoint,
            headers=headers,
            timeout=float(config.get("timeout", 30)),
        )


mcp_protocol_adapter = McpProtocolAdapter()
