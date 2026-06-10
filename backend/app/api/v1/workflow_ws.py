"""
工作流 WebSocket 路由。

实时推送工作流节点状态与执行进度。
"""

import logging
from typing import Optional

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect

from app.core.security import decode_access_token
from app.services.workflow.ws_manager import workflow_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/workflows", tags=["工作流 WebSocket"])


@router.websocket("/ws/{execution_id}")
async def workflow_execution_ws(
    websocket: WebSocket,
    execution_id: int,
    token: Optional[str] = Query(default=None, description="JWT 认证令牌"),
) -> None:
    """
    工作流执行实时状态 WebSocket。

    客户端通过 query 参数传递 token 进行认证。
    消息格式：{"type": "node_status"|"execution_status", ...}
    """
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await workflow_ws_manager.connect(execution_id, websocket)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "execution_id": execution_id,
                "message": "WebSocket 连接成功",
            }
        )

        while True:
            # 保持连接，接收客户端心跳
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("WebSocket 客户端断开 execution_id=%s", execution_id)
    except Exception as exc:
        logger.warning("WebSocket 异常 execution_id=%s: %s", execution_id, exc)
    finally:
        await workflow_ws_manager.disconnect(execution_id, websocket)
