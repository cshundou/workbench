"""
群聊式多 Agent 协同 API 路由。
"""

import logging
from typing import Annotated, Any, Literal, Optional

from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import (
    CurrentUser,
    get_current_tenant_id,
    get_db_session,
    require_permission,
)
from app.core.permissions import WF_READ, WF_WRITE
from app.core.response import success_response
from app.core.security import decode_access_token
from app.schemas.group_chat import GroupChatSessionCreate, GroupChatUserMessage
from app.schemas.professional_role import TeamAdjustRequest, TeamBuildRequest
from app.services.workflow.group_chat_service import group_chat_service
from app.services.workflow.group_chat_ws_manager import group_chat_ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/group-chat", tags=["群聊协同"])


class GroupChatResolveRequest(BaseModel):
    """人工审核处理请求。"""

    action: Literal["approve", "reject"]
    comment: Optional[str] = Field(default=None, max_length=2000)


class GroupChatInterveneRequest(BaseModel):
    """失败态人工介入请求。"""

    action: Literal["supplement", "restart"] = Field(
        default="supplement",
        description="supplement=仅补充说明；restart=补充后重新执行",
    )
    message: Optional[str] = Field(default=None, max_length=4000)


@router.post("/sessions", summary="创建群聊协同会话")
async def create_group_chat_session(
    data: GroupChatSessionCreate,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """创建虚拟项目群并启动多 Agent 协同任务。"""
    result = await group_chat_service.create_session(db, tenant_id, current_user, data)
    await db.commit()
    return success_response(data=result.model_dump(), message="群聊会话已创建")


@router.get("/sessions/{session_id}", summary="获取群聊会话详情")
async def get_group_chat_session(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
    include_messages: bool = Query(default=True, description="是否包含消息列表"),
) -> dict[str, Any]:
    """获取群聊会话状态、成员、进度与消息。"""
    result = await group_chat_service.get_session(
        db, session_id, tenant_id, include_messages=include_messages
    )
    return success_response(data=result.model_dump())


@router.get("/sessions/{session_id}/messages", summary="获取群聊消息列表")
async def list_group_chat_messages(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """获取会话全部消息（断线重连同步）。"""
    messages = await group_chat_service.list_messages(db, session_id, tenant_id)
    return success_response(data=[m.model_dump() for m in messages])


@router.post("/sessions/{session_id}/messages", summary="用户发言")
async def send_group_chat_message(
    session_id: int,
    data: GroupChatUserMessage,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """用户在项目群中发言补充信息。"""
    result = await group_chat_service.send_user_message(
        db, session_id, tenant_id, data
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="发言成功")


@router.post("/sessions/{session_id}/adjust-team", summary="调整团队成员")
async def adjust_group_chat_team(
    session_id: int,
    body: TeamAdjustRequest,
    _: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """执行中调整团队成员与分工。"""
    members = [m.model_dump() for m in body.members]
    result = await group_chat_service.adjust_team(db, session_id, tenant_id, members)
    await db.commit()
    return success_response(data=result.model_dump(), message="团队已调整")


@router.post("/team/preview", summary="预览智能组队结果")
async def preview_team_build(
    data: TeamBuildRequest,
    _: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
) -> dict[str, Any]:
    """预览任务驱动的智能组队结果（不创建会话）。"""
    from app.services.workflow.team_builder import team_builder

    custom = data.team_config.model_dump() if data.team_config else None
    config = team_builder.build(
        data.task,
        template_id=data.template_id,
        custom_config=custom,
    )
    return success_response(data=config)


@router.post("/sessions/{session_id}/cancel", summary="取消群聊会话")
async def cancel_group_chat_session(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """取消正在运行的群聊协同任务。"""
    result = await group_chat_service.cancel_session(db, session_id, tenant_id)
    await db.commit()
    return success_response(data=result.model_dump(), message="会话已取消")


@router.post("/sessions/{session_id}/restart", summary="重新执行群聊会话")
async def restart_group_chat_session(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """重新执行失败或已取消的群聊协同任务。"""
    _ = current_user
    result = await group_chat_service.restart_session(db, session_id, tenant_id)
    await db.commit()
    return success_response(data=result.model_dump(), message="已重新启动协作")


@router.post("/sessions/{session_id}/intervene", summary="失败态人工介入")
async def intervene_group_chat_session(
    session_id: int,
    body: GroupChatInterveneRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """失败或取消状态下补充说明，或补充后重新执行。"""
    _ = current_user
    result = await group_chat_service.intervene_session(
        db,
        session_id,
        tenant_id,
        body.action,
        body.message,
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="介入处理完成")


@router.post("/sessions/{session_id}/resolve", summary="人工审核处理")
async def resolve_group_chat_review(
    session_id: int,
    body: GroupChatResolveRequest,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_WRITE))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """批准或驳回处于人工审核状态的群聊会话。"""
    result = await group_chat_service.resolve_human_review(
        db, session_id, tenant_id, body.action, body.comment
    )
    await db.commit()
    return success_response(data=result.model_dump(), message="审核处理完成")


@router.get("/sessions/{session_id}/audit-logs", summary="导出群聊操作审计日志")
async def export_group_chat_audit_logs(
    session_id: int,
    current_user: Annotated[CurrentUser, Depends(require_permission(WF_READ))],
    tenant_id: Annotated[int, Depends(get_current_tenant_id)],
    db: Annotated[AsyncSession, Depends(get_db_session)],
) -> dict[str, Any]:
    """查询并导出群聊会话全场景审计埋点。"""
    logs = await group_chat_service.export_session_audit_logs(db, session_id, tenant_id)
    return success_response(data={"items": logs, "total": len(logs)})


@router.websocket("/ws/{session_id}")
async def group_chat_ws(
    websocket: WebSocket,
    session_id: int,
    token: Optional[str] = Query(default=None, description="JWT 认证令牌"),
) -> None:
    """
    群聊实时消息 WebSocket。

    消息格式：
    - group_chat_message: Agent/用户消息
    - member_status: 成员状态变更
    - session_update: 会话进度与状态
    """
    if not token:
        await websocket.close(code=4001, reason="Missing token")
        return

    payload = decode_access_token(token)
    if payload is None:
        await websocket.close(code=4001, reason="Invalid token")
        return

    await group_chat_ws_manager.connect(session_id, websocket)

    try:
        await websocket.send_json(
            {
                "type": "connected",
                "session_id": session_id,
                "message": "群聊 WebSocket 连接成功",
            }
        )

        while True:
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info("群聊 WebSocket 断开 session_id=%s", session_id)
    except Exception as exc:
        logger.warning("群聊 WebSocket 异常 session_id=%s: %s", session_id, exc)
    finally:
        await group_chat_ws_manager.disconnect(session_id, websocket)
