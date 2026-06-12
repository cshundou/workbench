"""
MCP HTTP 传输层实现。

支持 MCP Streamable HTTP 传输（JSON-RPC + SSE），严格遵循标准协议。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Optional

import httpx

from app.services.mcp.mcp_protocol import (
    MCP_METHOD_INITIALIZED,
    MCP_METHOD_INITIALIZE,
    McpProtocolError,
    build_initialize_params,
    build_jsonrpc_notification,
    build_jsonrpc_request,
    negotiate_protocol_version,
    parse_jsonrpc_response,
)

logger = logging.getLogger(__name__)


class McpHttpTransport:
    """MCP HTTP 传输客户端。"""

    def __init__(
        self,
        endpoint: str,
        *,
        headers: Optional[dict[str, str]] = None,
        timeout: float = 30.0,
    ) -> None:
        self.endpoint = endpoint.rstrip("/")
        self.headers = headers or {}
        self.timeout = timeout
        self._session_id: Optional[str] = None
        self._initialized = False
        self._protocol_version: Optional[str] = None

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def protocol_version(self) -> Optional[str]:
        return self._protocol_version

    async def _rpc(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        is_notification: bool = False,
    ) -> Any:
        """发送 JSON-RPC 请求或通知。"""
        payload = (
            build_jsonrpc_notification(method, params)
            if is_notification
            else build_jsonrpc_request(method, params)
        )
        request_headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            **self.headers,
        }
        if self._session_id:
            request_headers["Mcp-Session-Id"] = self._session_id

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint,
                    json=payload,
                    headers=request_headers,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("MCP HTTP 请求失败 method=%s: %s", method, exc)
            raise McpProtocolError(f"MCP HTTP 请求失败: {exc}") from exc

        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id

        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            data = self._parse_sse_payload(response.text)
        else:
            try:
                data = response.json()
            except json.JSONDecodeError as exc:
                raise McpProtocolError(f"MCP 响应非合法 JSON: {exc}") from exc

        if is_notification:
            return None
        return parse_jsonrpc_response(data)

    @staticmethod
    def _parse_sse_payload(text: str) -> dict[str, Any]:
        """从 SSE 响应中提取 JSON-RPC 消息。"""
        last_message: dict[str, Any] = {}
        for line in text.splitlines():
            if not line.startswith("data:"):
                continue
            raw = line[5:].strip()
            if not raw:
                continue
            try:
                last_message = json.loads(raw)
            except json.JSONDecodeError:
                continue
        if not last_message:
            raise McpProtocolError("MCP SSE 响应为空")
        return last_message

    async def initialize(self) -> dict[str, Any]:
        """执行 MCP 握手。"""
        result = await self._rpc(
            MCP_METHOD_INITIALIZE,
            build_initialize_params(),
        )
        if not isinstance(result, dict):
            raise McpProtocolError("initialize 响应格式无效")

        server_version = str(result.get("protocolVersion", ""))
        self._protocol_version = negotiate_protocol_version(server_version)
        await self._rpc(MCP_METHOD_INITIALIZED, {}, is_notification=True)
        self._initialized = True
        logger.info(
            "MCP HTTP 会话已初始化 endpoint=%s protocol=%s",
            self.endpoint,
            self._protocol_version,
        )
        return result

    async def request(self, method: str, params: Optional[dict[str, Any]] = None) -> Any:
        """发送标准 MCP JSON-RPC 请求。"""
        if not self._initialized and method != MCP_METHOD_INITIALIZE:
            await self.initialize()
        return await self._rpc(method, params)

    async def close(self) -> None:
        """关闭 HTTP 会话。"""
        self._session_id = None
        self._initialized = False
        logger.debug("MCP HTTP 会话已关闭 endpoint=%s", self.endpoint)


# 向后兼容别名
McpHttpClient = McpHttpTransport
