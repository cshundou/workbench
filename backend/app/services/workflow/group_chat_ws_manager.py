"""
群聊 WebSocket 连接管理器。
"""

import asyncio
import json
import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class GroupChatWebSocketManager:
    """群聊会话 WebSocket 连接池。"""

    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = {}
        self._lock = asyncio.Lock()

    async def connect(self, session_id: int, websocket: WebSocket) -> None:
        """注册 WebSocket 连接。"""
        await websocket.accept()
        async with self._lock:
            if session_id not in self._connections:
                self._connections[session_id] = set()
            self._connections[session_id].add(websocket)
        logger.info("群聊 WebSocket 已连接 session_id=%s", session_id)

    async def disconnect(self, session_id: int, websocket: WebSocket) -> None:
        """移除 WebSocket 连接。"""
        async with self._lock:
            conns = self._connections.get(session_id)
            if conns and websocket in conns:
                conns.discard(websocket)
            if conns is not None and len(conns) == 0:
                del self._connections[session_id]
        logger.info("群聊 WebSocket 已断开 session_id=%s", session_id)

    async def broadcast(self, session_id: int, message: dict[str, Any]) -> None:
        """向指定会话的所有连接广播消息。"""
        from app.services.workflow.group_chat_ws_event_bus import group_chat_ws_event_bus

        group_chat_ws_event_bus.publish(session_id, message)

    async def broadcast_local(self, session_id: int, message: dict[str, Any]) -> None:
        """向本进程 WebSocket 连接直接广播。"""
        async with self._lock:
            connections = list(self._connections.get(session_id, set()))

        if not connections:
            return

        payload = json.dumps(message, default=str, ensure_ascii=False)
        dead: list[WebSocket] = []
        for ws in connections:
            try:
                await ws.send_text(payload)
            except Exception as exc:
                logger.warning("群聊 WS 推送失败 session_id=%s: %s", session_id, exc)
                dead.append(ws)

        if dead:
            async with self._lock:
                conns = self._connections.get(session_id)
                if conns:
                    for ws in dead:
                        conns.discard(ws)


group_chat_ws_manager = GroupChatWebSocketManager()
