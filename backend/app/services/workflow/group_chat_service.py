"""
群聊式多 Agent 协同业务服务。
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.task_queue import enqueue_task
from app.models.group_chat import GroupChatMessage, GroupChatSession
from app.models.user import User
from app.models.workflow import Workflow
from app.schemas.group_chat import (
    GroupChatMemberInfo,
    GroupChatMessageResponse,
    GroupChatProgressStep,
    GroupChatSessionCreate,
    GroupChatSessionDetailResponse,
    GroupChatSessionResponse,
    GroupChatUserMessage,
)
from app.core.guardrails import guardrails_service
from app.services.user_key_context import user_key_resolver
from app.services.workflow.group_chat_engine import GroupChatEngine
from app.services.workflow.group_chat_ws_manager import group_chat_ws_manager

logger = logging.getLogger(__name__)

_cancelled_sessions: set[int] = set()


class GroupChatService:
    """群聊协同服务。"""

    async def create_session(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: GroupChatSessionCreate,
    ) -> GroupChatSessionResponse:
        """创建群聊会话并异步启动协同任务。"""
        await guardrails_service.validate_user_input(data.task)

        workflow_id = data.workflow_id
        if workflow_id is not None:
            wf_stmt = select(Workflow).where(
                Workflow.id == workflow_id,
                Workflow.tenant_id == tenant_id,
            )
            workflow = (await db.execute(wf_stmt)).scalar_one_or_none()
            if workflow is None:
                raise NotFoundError(message="工作流不存在")

        title = data.title or data.task[:50]
        session = GroupChatSession(
            tenant_id=tenant_id,
            user_id=user.id,
            workflow_id=workflow_id,
            title=title,
            task_description=data.task,
            status="pending",
            progress=0.0,
            kb_id=data.kb_id,
            extra_params={},
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        thread_id = f"group_chat_{session.id}"
        task_id = await enqueue_task(
            "execute_group_chat_task",
            session.id,
            tenant_id,
            user.id,
            data.task,
            data.kb_id,
            thread_id,
        )
        session.extra_params = {"thread_id": thread_id, "task_id": task_id}
        await db.flush()

        logger.info("群聊会话已创建 session_id=%s task_id=%s", session.id, task_id)
        return self._to_session_response(session)

    async def get_session(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        *,
        include_messages: bool = False,
    ) -> GroupChatSessionDetailResponse | GroupChatSessionResponse:
        """获取群聊会话详情。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if include_messages:
            stmt = (
                select(GroupChatSession)
                .where(GroupChatSession.id == session_id)
                .options(selectinload(GroupChatSession.messages))
            )
            session = (await db.execute(stmt)).scalar_one()
            return self._to_session_detail_response(session)
        return self._to_session_response(session)

    async def list_messages(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
    ) -> list[GroupChatMessageResponse]:
        """获取会话消息列表。"""
        await self._get_session_or_raise(db, session_id, tenant_id)
        stmt = (
            select(GroupChatMessage)
            .where(GroupChatMessage.session_id == session_id)
            .order_by(GroupChatMessage.id)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [GroupChatMessageResponse.model_validate(row) for row in rows]

    async def send_user_message(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        data: GroupChatUserMessage,
    ) -> GroupChatMessageResponse:
        """用户发言补充信息。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status in ("completed", "failed"):
            raise ValidationError(message="会话已结束，无法发言")

        await guardrails_service.validate_user_input(data.content)

        message_payload = {
            "id": f"user-{session_id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "sender": {
                "id": "user",
                "name": "用户",
                "role": "user",
                "avatar": "👤",
            },
            "type": "question",
            "content": data.content,
            "attachments": [],
            "metadata": {},
        }
        msg = await self._persist_message(
            db, session, "user", "question", data.content, message_payload
        )

        supplements = list(session.extra_params.get("user_supplements") or [])
        supplements.append(data.content)
        extra = dict(session.extra_params)
        extra["user_supplements"] = supplements
        session.extra_params = extra
        await db.flush()

        await group_chat_ws_manager.broadcast(
            session_id,
            {"type": "group_chat_message", "message": message_payload},
        )
        await group_chat_ws_manager.broadcast(
            session_id,
            {"type": "session_update", "status": session.status, "progress": session.progress},
        )
        return GroupChatMessageResponse.model_validate(msg)

    def is_session_cancelled(self, session_id: int) -> bool:
        """检查会话是否已取消。"""
        return session_id in _cancelled_sessions

    async def run_group_chat_task(
        self,
        session_id: int,
        tenant_id: int,
        user_id: int,
        task: str,
        kb_id: Optional[int],
        thread_id: str,
    ) -> None:
        """在后台任务中执行群聊协同 LangGraph。"""
        from app.core.database import async_session_factory

        main_loop = asyncio.get_running_loop()
        member_statuses: dict[str, str] = {}

        async def persist_and_broadcast(message: dict[str, Any]) -> None:
            async with async_session_factory() as db:
                stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
                session = (await db.execute(stmt)).scalar_one_or_none()
                if session is None:
                    return
                role = message.get("sender", {}).get("role", "system")
                await self._persist_message(
                    db,
                    session,
                    role,
                    message.get("type", "progress_update"),
                    message.get("content", ""),
                    message,
                )
                session.progress = float(message.get("metadata", {}).get("progress", session.progress))
                await db.commit()

            await group_chat_ws_manager.broadcast(
                session_id,
                {"type": "group_chat_message", "message": message},
            )

        def message_callback(message: dict[str, Any]) -> None:
            asyncio.run_coroutine_threadsafe(persist_and_broadcast(message), main_loop)

        def member_status_callback(role: str, status: str) -> None:
            member_statuses[role] = status
            asyncio.run_coroutine_threadsafe(
                group_chat_ws_manager.broadcast(
                    session_id,
                    {
                        "type": "member_status",
                        "role": role,
                        "status": status,
                        "members": GroupChatEngine.get_members(member_statuses),
                    },
                ),
                main_loop,
            )

        try:
            async with async_session_factory() as db:
                stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
                session = (await db.execute(stmt)).scalar_one()
                session.status = "running"
                await db.commit()

            await group_chat_ws_manager.broadcast(
                session_id,
                {"type": "session_update", "status": "running", "progress": 0},
            )

            user_ctx = None
            async with async_session_factory() as db:
                user_ctx = await user_key_resolver.load_context(db, user_id, tenant_id)

            engine = GroupChatEngine(settings.redis_url, user_ctx=user_ctx)
            engine.set_execution_context(tenant_id, user_id, session_id)
            engine.set_message_callback(message_callback)
            engine.set_member_status_callback(member_status_callback)

            graph = engine.build_graph()
            initial_state: dict[str, Any] = {
                "task": task,
                "kb_id": kb_id,
                "subtasks": [],
                "results": {},
                "deliverables": [],
                "status": "pending",
                "progress": 0.0,
                "current_step": 0,
                "current_subtask_index": 0,
                "review_count": 0,
                "review_result": None,
                "user_supplements": [],
                "error": "",
                "final_answer": "",
                "member_statuses": {},
            }
            config = {"configurable": {"thread_id": thread_id}}

            if self.is_session_cancelled(session_id):
                await self._mark_session_failed(session_id, "会话已被用户取消")
                return

            loop = asyncio.get_event_loop()

            def _invoke() -> dict[str, Any]:
                return graph.invoke(initial_state, config)

            final_state = await asyncio.wait_for(
                loop.run_in_executor(None, _invoke),
                timeout=settings.workflow_execution_timeout_seconds,
            )

            await self._finalize_session(session_id, final_state)
        except asyncio.TimeoutError:
            await self._mark_session_failed(
                session_id,
                f"群聊协同执行超时（{settings.workflow_execution_timeout_seconds}秒）",
            )
        except Exception as exc:
            logger.exception("群聊协同执行失败 session_id=%s: %s", session_id, exc)
            await self._mark_session_failed(session_id, str(exc))

    async def _finalize_session(
        self, session_id: int, final_state: dict[str, Any]
    ) -> None:
        """持久化最终会话状态。"""
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
            session = (await db.execute(stmt)).scalar_one()
            session.status = final_state.get("status", "completed")
            session.progress = float(final_state.get("progress", 100.0))
            session.subtasks = final_state.get("subtasks", [])
            session.deliverables = final_state.get("deliverables", [])
            session.review_result = final_state.get("review_result")
            session.review_count = int(final_state.get("review_count") or 0)
            session.error_message = final_state.get("error") or None
            if session.status in ("completed", "failed", "human_review"):
                session.completed_at = datetime.now(timezone.utc)
            await db.commit()

        await group_chat_ws_manager.broadcast(
            session_id,
            {
                "type": "session_update",
                "status": final_state.get("status"),
                "progress": final_state.get("progress"),
                "final_answer": final_state.get("final_answer"),
            },
        )

    async def _mark_session_failed(self, session_id: int, error: str) -> None:
        """标记会话失败。"""
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
            session = (await db.execute(stmt)).scalar_one_or_none()
            if session is None:
                return
            session.status = "failed"
            session.error_message = error
            session.completed_at = datetime.now(timezone.utc)
            await db.commit()

        await group_chat_ws_manager.broadcast(
            session_id,
            {"type": "session_update", "status": "failed", "error": error},
        )

    async def _persist_message(
        self,
        db: AsyncSession,
        session: GroupChatSession,
        sender_role: str,
        message_type: str,
        content: str,
        payload: dict[str, Any],
    ) -> GroupChatMessage:
        """持久化群聊消息。"""
        msg = GroupChatMessage(
            session_id=session.id,
            message_id=payload.get("id", f"msg-{session.id}-{datetime.now(timezone.utc).timestamp()}"),
            sender_role=sender_role,
            message_type=message_type,
            content=content,
            payload=payload,
        )
        db.add(msg)
        await db.flush()
        return msg

    async def _get_session_or_raise(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
    ) -> GroupChatSession:
        """获取会话或抛出异常。"""
        stmt = select(GroupChatSession).where(
            GroupChatSession.id == session_id,
            GroupChatSession.tenant_id == tenant_id,
        )
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None:
            raise NotFoundError(message="群聊会话不存在")
        return session

    def _to_session_response(self, session: GroupChatSession) -> GroupChatSessionResponse:
        """转换为会话响应。"""
        member_statuses = (session.extra_params or {}).get("member_statuses") or {}
        return GroupChatSessionResponse(
            id=session.id,
            tenant_id=session.tenant_id,
            user_id=session.user_id,
            workflow_id=session.workflow_id,
            execution_id=session.execution_id,
            title=session.title,
            task_description=session.task_description,
            status=session.status,
            progress=float(session.progress),
            current_step=session.current_step,
            subtasks=session.subtasks or [],
            deliverables=session.deliverables or [],
            review_result=session.review_result,
            review_count=session.review_count,
            kb_id=session.kb_id,
            error_message=session.error_message,
            completed_at=session.completed_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
            members=[
                GroupChatMemberInfo(**m)
                for m in GroupChatEngine.get_members(member_statuses)
            ],
            progress_steps=[
                GroupChatProgressStep(**s)
                for s in GroupChatEngine.get_progress_steps(
                    session.status, session.subtasks or []
                )
            ],
        )

    def _to_session_detail_response(
        self, session: GroupChatSession
    ) -> GroupChatSessionDetailResponse:
        """转换为含消息的会话详情响应。"""
        base = self._to_session_response(session)
        messages = [
            GroupChatMessageResponse.model_validate(m) for m in (session.messages or [])
        ]
        return GroupChatSessionDetailResponse(**base.model_dump(), messages=messages)


group_chat_service = GroupChatService()
