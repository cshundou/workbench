"""
工作流 WebSocket 连接管理器。

维护执行实例与 WebSocket 连接的映射，用于实时推送节点状态。
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class WorkflowWebSocketManager:
    """工作流执行 WebSocket 连接池。"""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, execution_id: int, websocket: WebSocket) -> None:
        """注册 WebSocket 连接。"""
        await websocket.accept()
        async with self._lock:
            if execution_id not in self._connections:
                self._connections[execution_id] = set()
            self._connections[execution_id].add(websocket)
        logger.info("WebSocket 已连接 execution_id=%s", execution_id)

    async def disconnect(self, execution_id: int, websocket: WebSocket) -> None:
        """移除 WebSocket 连接。"""
        async with self._lock:
            conns = self._connections.get(execution_id)
            if conns and websocket in conns:
                conns.discard(websocket)
            if conns is not None and len(conns) == 0:
                del self._connections[execution_id]
        logger.info("WebSocket 已断开 execution_id=%s", execution_id)

    async def broadcast(self, execution_id: int, message: dict[str, Any]) -> None:
        """向指定执行实例的所有连接广播消息。"""
        async with self._lock:
            connections = list(self._connections.get(execution_id, set()))

        if not connections:
            return

        payload = json.dumps(message, default=str)
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.warning(
                    "WebSocket 推送失败 execution_id=%s: %s", execution_id, exc
                )
                dead.append(ws)

        if dead:
            async with self._lock:
                conns = self._connections.get(execution_id)
                if conns:
                    for ws in dead:
                        conns.discard(ws)

    async def broadcast_node_status(
        self,
        execution_id: int,
        node_id: str,
        status: str,
        log_entry: dict[str, Any] | None = None,
    ) -> None:
        """推送节点状态变更。"""
        message: dict[str, Any] = {
            "type": "node_status",
            "execution_id": execution_id,
            "node_id": node_id,
            "status": status,
        }
        if log_entry:
            message["log"] = log_entry
        await self.broadcast(execution_id, message)

    async def broadcast_execution_status(
        self,
        execution_id: int,
        status: str,
        data: dict[str, Any] | None = None,
    ) -> None:
        """推送工作流整体状态变更。"""
        message: dict[str, Any] = {
            "type": "execution_status",
            "execution_id": execution_id,
            "status": status,
        }
        if data:
            message["data"] = data
        await self.broadcast(execution_id, message)


workflow_ws_manager = WorkflowWebSocketManager()
