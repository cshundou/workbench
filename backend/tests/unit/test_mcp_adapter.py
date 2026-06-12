"""MCP 协议适配器单元测试。"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.mcp.mcp_adapter import McpProtocolAdapter, McpSession
from app.services.mcp.mcp_http_transport import McpHttpTransport
from app.services.mcp.mcp_protocol import (
    MCP_PROTOCOL_VERSION,
    McpCallToolResult,
    McpProtocolError,
    McpToolDefinition,
    build_initialize_params,
    build_jsonrpc_request,
    parse_jsonrpc_response,
)
from app.services.mcp.mcp_stdio_transport import McpStdioTransport


class TestMcpProtocol:
    """MCP 标准协议工具函数。"""

    def test_build_initialize_params(self) -> None:
        params = build_initialize_params()
        assert params["protocolVersion"] == MCP_PROTOCOL_VERSION
        assert "clientInfo" in params
        assert "capabilities" in params

    def test_build_jsonrpc_request(self) -> None:
        req = build_jsonrpc_request("tools/list", {})
        assert req["jsonrpc"] == "2.0"
        assert req["method"] == "tools/list"
        assert "id" in req

    def test_parse_jsonrpc_response_success(self) -> None:
        result = parse_jsonrpc_response({"jsonrpc": "2.0", "id": "1", "result": {"tools": []}})
        assert result == {"tools": []}

    def test_parse_jsonrpc_response_error(self) -> None:
        with pytest.raises(McpProtocolError) as exc_info:
            parse_jsonrpc_response(
                {
                    "jsonrpc": "2.0",
                    "id": "1",
                    "error": {"code": -32601, "message": "Method not found"},
                }
            )
        assert exc_info.value.code == -32601

    def test_tool_definition_from_dict(self) -> None:
        tool = McpToolDefinition.from_dict(
            {
                "name": "search",
                "description": "Search web",
                "inputSchema": {"type": "object", "properties": {"q": {"type": "string"}}},
            }
        )
        assert tool.name == "search"
        assert tool.input_schema["type"] == "object"

    def test_call_tool_result_to_text(self) -> None:
        result = McpCallToolResult.from_dict(
            {
                "content": [{"type": "text", "text": "hello"}],
                "isError": False,
            }
        )
        assert result.to_text() == "hello"


class TestMcpHttpTransport:
    """HTTP 传输层。"""

    @pytest.mark.asyncio
    async def test_initialize_and_list_tools(self) -> None:
        transport = McpHttpTransport("http://localhost:9999/mcp")
        init_response = MagicMock()
        init_response.headers = {"content-type": "application/json"}
        init_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "1",
            "result": {
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "test", "version": "1.0"},
            },
        }
        tools_response = MagicMock()
        tools_response.headers = {"content-type": "application/json"}
        tools_response.json.return_value = {
            "jsonrpc": "2.0",
            "id": "2",
            "result": {"tools": [{"name": "calc", "inputSchema": {}}]},
        }
        init_response.raise_for_status = MagicMock()
        tools_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.post = AsyncMock(side_effect=[init_response, init_response, tools_response])
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "app.services.mcp.mcp_http_transport.httpx.AsyncClient",
            return_value=mock_client,
        ):
            await transport.initialize()
            result = await transport.request("tools/list", {})
        assert result["tools"][0]["name"] == "calc"

    def test_parse_sse_payload(self) -> None:
        sse_text = 'event: message\ndata: {"jsonrpc":"2.0","id":"1","result":{"tools":[]}}\n\n'
        data = McpHttpTransport._parse_sse_payload(sse_text)
        parsed = parse_jsonrpc_response(data)
        assert parsed == {"tools": []}


class TestMcpProtocolAdapter:
    """MCP 协议适配器。"""

    @pytest.fixture
    def adapter(self) -> McpProtocolAdapter:
        return McpProtocolAdapter()

    @pytest.mark.asyncio
    async def test_list_tools_via_adapter(self, adapter: McpProtocolAdapter) -> None:
        mock_transport = AsyncMock()
        mock_transport.initialize = AsyncMock(
            return_value={
                "protocolVersion": MCP_PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "mock", "version": "1.0"},
            }
        )
        mock_transport.protocol_version = MCP_PROTOCOL_VERSION
        mock_transport.request = AsyncMock(
            return_value={"tools": [{"name": "weather", "inputSchema": {}}]}
        )
        mock_transport.close = AsyncMock()

        server = MagicMock()
        server.id = 1
        server.name = "mock"
        server.transport = "http"
        server.endpoint = "http://localhost/mcp"
        server.config = {}

        with patch.object(adapter, "_create_transport", return_value=mock_transport):
            session = await adapter.connect(server)
            tools = await adapter.list_tools(session)
            await adapter.disconnect(session)

        assert len(tools) == 1
        assert tools[0].name == "weather"
        mock_transport.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_call_tool_error_raises(self, adapter: McpProtocolAdapter) -> None:
        session = McpSession(1, AsyncMock(), MagicMock())
        session.transport.request = AsyncMock(
            return_value={
                "content": [{"type": "text", "text": "invalid args"}],
                "isError": True,
            }
        )
        with pytest.raises(McpProtocolError):
            await adapter.call_tool(session, "bad_tool", {})

    def test_create_stdio_transport(self, adapter: McpProtocolAdapter) -> None:
        server = MagicMock()
        server.transport = "stdio"
        server.endpoint = "npx"
        server.config = {"command": "npx", "args": ["-y", "pkg"]}
        transport = adapter._create_transport(server)
        assert isinstance(transport, McpStdioTransport)

    def test_create_http_transport(self, adapter: McpProtocolAdapter) -> None:
        server = MagicMock()
        server.transport = "http"
        server.endpoint = "http://localhost/mcp"
        server.config = {"auth_token": "secret"}
        transport = adapter._create_transport(server)
        assert isinstance(transport, McpHttpTransport)


class TestMcpServicePresets:
    """MCP 服务预设。"""

    def test_builtin_presets_use_standard_transports(self) -> None:
        from app.services.mcp.mcp_service import BUILTIN_MCP_PRESETS

        transports = {p["transport"] for p in BUILTIN_MCP_PRESETS}
        assert transports <= {"http", "stdio"}
        assert len(BUILTIN_MCP_PRESETS) >= 3
