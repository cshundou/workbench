"""
MCP stdio 传输层实现。

通过子进程 stdin/stdout 与 MCP 服务器通信，遵循 newline-delimited JSON-RPC 规范。
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

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


class McpStdioTransport:
    """MCP stdio 传输客户端。"""

    def __init__(
        self,
        command: str,
        args: Optional[list[str]] = None,
        *,
        env: Optional[dict[str, str]] = None,
        cwd: Optional[str] = None,
        timeout: float = 60.0,
    ) -> None:
        self.command = command
        self.args = args or []
        self.env = env
        self.cwd = cwd
        self.timeout = timeout
        self._process: Optional[asyncio.subprocess.Process] = None
        self._write_lock = asyncio.Lock()
        self._initialized = False
        self._protocol_version: Optional[str] = None

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    @property
    def protocol_version(self) -> Optional[str]:
        return self._protocol_version

    async def start(self) -> None:
        """启动 MCP 子进程。"""
        if self._process is not None:
            return
        try:
            self._process = await asyncio.create_subprocess_exec(
                self.command,
                *self.args,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=self.env,
                cwd=self.cwd,
            )
            logger.info(
                "MCP stdio 进程已启动 command=%s args=%s pid=%s",
                self.command,
                self.args,
                self._process.pid,
            )
        except OSError as exc:
            logger.exception("MCP stdio 进程启动失败: %s", exc)
            raise McpProtocolError(f"无法启动 MCP 进程: {exc}") from exc

    async def _send(self, payload: dict[str, Any]) -> None:
        """写入一条 JSON-RPC 消息。"""
        if self._process is None or self._process.stdin is None:
            raise McpProtocolError("MCP stdio 进程未启动")
        line = json.dumps(payload, ensure_ascii=False) + "\n"
        async with self._write_lock:
            self._process.stdin.write(line.encode("utf-8"))
            await self._process.stdin.drain()

    async def _receive(self) -> dict[str, Any]:
        """读取一条 JSON-RPC 响应。"""
        if self._process is None or self._process.stdout is None:
            raise McpProtocolError("MCP stdio 进程未启动")
        try:
            line = await asyncio.wait_for(
                self._process.stdout.readline(),
                timeout=self.timeout,
            )
        except asyncio.TimeoutError as exc:
            raise McpProtocolError(f"MCP stdio 读取超时（{self.timeout}s）") from exc

        if not line:
            stderr = await self._read_stderr()
            raise McpProtocolError(
                f"MCP stdio 进程已退出{': ' + stderr if stderr else ''}"
            )
        try:
            return json.loads(line.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise McpProtocolError(f"MCP stdio 响应非合法 JSON: {exc}") from exc

    async def _read_stderr(self) -> str:
        """读取 stderr 便于诊断。"""
        if self._process is None or self._process.stderr is None:
            return ""
        try:
            data = await asyncio.wait_for(self._process.stderr.read(4096), timeout=1.0)
            return data.decode("utf-8", errors="replace").strip()
        except Exception:
            return ""

    async def _rpc(
        self,
        method: str,
        params: Optional[dict[str, Any]] = None,
        *,
        is_notification: bool = False,
    ) -> Any:
        """发送 JSON-RPC 请求并等待响应。"""
        payload = (
            build_jsonrpc_notification(method, params)
            if is_notification
            else build_jsonrpc_request(method, params)
        )
        await self._send(payload)
        if is_notification:
            return None
        response = await self._receive()
        return parse_jsonrpc_response(response)

    async def initialize(self) -> dict[str, Any]:
        """执行 MCP 握手。"""
        await self.start()
        result = await self._rpc(MCP_METHOD_INITIALIZE, build_initialize_params())
        if not isinstance(result, dict):
            raise McpProtocolError("initialize 响应格式无效")

        server_version = str(result.get("protocolVersion", ""))
        self._protocol_version = negotiate_protocol_version(server_version)
        await self._rpc(MCP_METHOD_INITIALIZED, {}, is_notification=True)
        self._initialized = True
        logger.info(
            "MCP stdio 会话已初始化 command=%s protocol=%s",
            self.command,
            self._protocol_version,
        )
        return result

    async def request(self, method: str, params: Optional[dict[str, Any]] = None) -> Any:
        """发送标准 MCP JSON-RPC 请求。"""
        if not self._initialized and method != MCP_METHOD_INITIALIZE:
            await self.initialize()
        return await self._rpc(method, params)

    async def close(self) -> None:
        """终止 MCP 子进程。"""
        if self._process is None:
            return
        try:
            if self._process.returncode is None:
                self._process.terminate()
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                except asyncio.TimeoutError:
                    self._process.kill()
                    await self._process.wait()
        except ProcessLookupError:
            pass
        finally:
            logger.info("MCP stdio 进程已关闭 command=%s", self.command)
            self._process = None
            self._initialized = False
