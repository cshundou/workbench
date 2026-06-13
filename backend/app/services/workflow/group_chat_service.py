"""
群聊式多 Agent 协同业务服务。
"""

from __future__ import annotations

import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.core.exceptions import NotFoundError, ValidationError
from app.core.task_queue import enqueue_task
from app.models.audit_log import AuditLog
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
from app.services.audit_service import audit_service
from app.services.monitor_service import monitor_service
from app.services.user_key_context import user_key_resolver
from app.services.workflow.group_chat_engine import GroupChatEngine
from app.services.workflow.group_chat_ws_manager import group_chat_ws_manager
from app.services.workflow.team_builder import team_builder
from app.utils.error_translator import translate_error_message

logger = logging.getLogger(__name__)

_cancelled_sessions: set[int] = set()


class _SupplementBridge:
    """跨线程传递用户补充要求（API 写入 DB，Worker 轮询消费）。"""

    def __init__(self) -> None:
        self._pending: list[str] = []
        self._lock = threading.Lock()

    def push(self, items: list[str]) -> None:
        if not items:
            return
        with self._lock:
            self._pending.extend(items)

    def drain(self) -> list[str]:
        with self._lock:
            items = list(self._pending)
            self._pending.clear()
            return items


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

        # 智能组队：动态团队配置
        template_id = data.template_id
        if data.use_classic_five:
            template_id = "classic_five"
        team_config = team_builder.build(
            data.task,
            template_id=template_id,
            custom_config=data.team_config,
        )

        session = GroupChatSession(
            tenant_id=tenant_id,
            user_id=user.id,
            workflow_id=workflow_id,
            title=title,
            task_description=data.task,
            status="pending",
            progress=0.0,
            kb_id=data.kb_id,
            extra_params={"team_config": team_config},
        )
        db.add(session)
        await db.flush()
        await db.refresh(session)

        # 推送团队组建入场事件
        await group_chat_ws_manager.broadcast(
            session.id,
            {
                "type": "team_formation",
                "team_config": team_config,
                "message": "正在为您组建专属团队…",
            },
        )

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
        extra = dict(session.extra_params or {})
        extra.update({"thread_id": thread_id, "task_id": task_id})
        session.extra_params = extra
        await db.flush()

        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="group_chat.session_create",
            resource_type="group_chat_session",
            resource_id=session.id,
            detail={"task": data.task[:200], "workflow_id": workflow_id},
        )
        await monitor_service.record_group_chat_event("created")
        logger.info("群聊会话已创建 session_id=%s task_id=%s", session.id, task_id)
        return await self._build_session_response(db, session)

    async def get_session(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        *,
        include_messages: bool = False,
    ) -> GroupChatSessionDetailResponse | GroupChatSessionResponse:
        """获取群聊会话详情。"""
        stmt = select(GroupChatSession).where(
            GroupChatSession.id == session_id,
            GroupChatSession.tenant_id == tenant_id,
        )
        if include_messages:
            stmt = stmt.options(selectinload(GroupChatSession.messages))
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None:
            raise NotFoundError(message="群聊会话不存在")
        if include_messages:
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

    async def adjust_team(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        members: list[dict[str, Any]],
    ) -> GroupChatSessionResponse:
        """中途调整团队成员与分工。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status in ("completed", "failed", "cancelled"):
            raise ValidationError(message="会话已结束，无法调整团队")

        extra = dict(session.extra_params or {})
        team_config = dict(extra.get("team_config") or {})
        team_config["members"] = members
        team_config["team_size"] = len(members)
        extra["team_config"] = team_config
        session.extra_params = extra
        await db.flush()

        await group_chat_ws_manager.broadcast(
            session_id,
            {
                "type": "team_adjusted",
                "team_config": team_config,
                "members": GroupChatEngine.get_members(
                    team_config=team_config,
                    session_status=session.status,
                ),
            },
        )
        return await self._build_session_response(db, session)

    async def send_user_message(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        data: GroupChatUserMessage,
    ) -> GroupChatMessageResponse:
        """用户发言补充信息。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status == "completed":
            raise ValidationError(message="会话已结束，无法发言")
        if session.status == "failed":
            raise ValidationError(
                message="会话已失败，请通过下方输入补充说明（将走人工介入通道）"
            )

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
        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=session.user_id,
            action="group_chat.user_message",
            resource_type="group_chat_session",
            resource_id=session_id,
            detail={"content_length": len(data.content)},
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
        """检查会话是否已取消（进程内标记）。"""
        return session_id in _cancelled_sessions

    async def is_session_cancelled_db(
        self, db: AsyncSession, session_id: int
    ) -> bool:
        """检查会话是否已取消（含 DB 持久化标记）。"""
        if session_id in _cancelled_sessions:
            return True
        stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
        session = (await db.execute(stmt)).scalar_one_or_none()
        if session is None:
            return True
        extra = session.extra_params or {}
        return bool(extra.get("cancelled")) or session.status == "cancelled"

    async def cancel_session(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
    ) -> GroupChatSessionResponse:
        """取消正在运行的群聊会话。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status in ("completed", "failed", "cancelled"):
            raise ValidationError(message="会话已结束，无法取消")

        _cancelled_sessions.add(session_id)
        extra = dict(session.extra_params or {})
        extra["cancelled"] = True
        session.extra_params = extra
        session.status = "cancelled"
        session.error_message = "用户已取消协作"
        session.completed_at = datetime.now(timezone.utc)
        await db.flush()

        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=session.user_id,
            action="group_chat.session_cancel",
            resource_type="group_chat_session",
            resource_id=session_id,
        )
        await monitor_service.record_group_chat_event("cancelled")
        await group_chat_ws_manager.broadcast(
            session_id,
            {
                "type": "session_update",
                "status": "cancelled",
                "error": session.error_message,
            },
        )
        logger.info("群聊会话已取消 session_id=%s", session_id)
        return await self._build_session_response(db, session)

    async def restart_session(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
    ) -> GroupChatSessionResponse:
        """重新执行失败或已取消的群聊会话。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status not in ("failed", "cancelled"):
            raise ValidationError(message="仅失败或已取消的会话可重新执行")

        _cancelled_sessions.discard(session_id)
        extra = dict(session.extra_params or {})
        extra.pop("cancelled", None)
        subtasks = list(session.subtasks or [])
        for item in subtasks:
            if isinstance(item, dict) and item.get("status") in ("error", "completed"):
                if item.get("status") == "error":
                    item["status"] = "pending"

        session.status = "pending"
        session.progress = 0.0
        session.error_message = None
        session.completed_at = None
        session.subtasks = subtasks
        session.extra_params = extra
        await db.flush()

        thread_id = extra.get("thread_id") or f"group_chat_{session.id}"
        task_id = await enqueue_task(
            "execute_group_chat_task",
            session.id,
            tenant_id,
            session.user_id,
            session.task_description,
            session.kb_id,
            thread_id,
        )
        extra["task_id"] = task_id
        session.extra_params = extra
        await db.flush()

        await group_chat_ws_manager.broadcast(
            session_id,
            {"type": "session_update", "status": "pending", "progress": 0},
        )
        logger.info("群聊会话已重启 session_id=%s task_id=%s", session_id, task_id)
        return await self._build_session_response(db, session)

    async def intervene_session(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        action: str,
        message: Optional[str] = None,
    ) -> GroupChatSessionResponse:
        """失败态人工介入：补充说明或补充后重启。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status not in ("failed", "cancelled", "human_review"):
            raise ValidationError(message="当前状态不支持人工介入")

        if message:
            await guardrails_service.validate_user_input(message)
            supplements = list((session.extra_params or {}).get("user_supplements") or [])
            supplements.append(message)
            extra = dict(session.extra_params or {})
            extra["user_supplements"] = supplements
            session.extra_params = extra
            payload = {
                "id": f"user-intervene-{session_id}-{int(datetime.now(timezone.utc).timestamp() * 1000)}",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "sender": {
                    "id": "user",
                    "name": "用户",
                    "role": "user",
                    "avatar": "👤",
                },
                "type": "question",
                "content": message,
                "attachments": [],
                "metadata": {"intervention": True},
            }
            await self._persist_message(
                db,
                session,
                "user",
                "question",
                message,
                payload,
            )
            await db.flush()
            await group_chat_ws_manager.broadcast(
                session_id,
                {"type": "group_chat_message", "message": payload},
            )

        if action == "restart":
            await db.commit()
            return await self.restart_session(db, session_id, tenant_id)

        return await self._build_session_response(db, session)

    async def resolve_human_review(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        action: str,
        comment: Optional[str] = None,
    ) -> GroupChatSessionResponse:
        """处理人工审核（批准或驳回）。"""
        session = await self._get_session_or_raise(db, session_id, tenant_id)
        if session.status != "human_review":
            raise ValidationError(message="当前会话不在人工审核状态")

        if action == "approve":
            session.status = "completed"
            session.progress = 100.0
            session.error_message = None
            final_answer = self._build_summary_from_session(session)
            extra = dict(session.extra_params or {})
            extra["human_review_comment"] = comment
            extra["final_answer"] = final_answer
            session.extra_params = extra
            await self._persist_message(
                db,
                session,
                "auditor",
                "review_result",
                f"✅ 人工审核通过。{comment or ''}".strip(),
                {
                    "id": f"human-approve-{session_id}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sender": {
                        "id": "auditor",
                        "name": "审核员",
                        "role": "auditor",
                        "avatar": "✅",
                    },
                    "type": "review_result",
                    "content": f"人工审核通过。{comment or ''}".strip(),
                    "attachments": [],
                    "metadata": {"human_review": True, "action": "approve"},
                },
            )
        elif action == "reject":
            session.status = "failed"
            session.error_message = comment or "人工审核驳回"
            await self._persist_message(
                db,
                session,
                "auditor",
                "review_result",
                f"❌ 人工审核驳回。{session.error_message}",
                {
                    "id": f"human-reject-{session_id}",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "sender": {
                        "id": "auditor",
                        "name": "审核员",
                        "role": "auditor",
                        "avatar": "✅",
                    },
                    "type": "review_result",
                    "content": session.error_message,
                    "attachments": [],
                    "metadata": {"human_review": True, "action": "reject"},
                },
            )
        else:
            raise ValidationError(message="action 必须为 approve 或 reject")

        session.completed_at = datetime.now(timezone.utc)
        await db.flush()

        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=session.user_id,
            action=f"group_chat.human_{action}",
            resource_type="group_chat_session",
            resource_id=session_id,
            detail={"comment": comment},
        )
        await group_chat_ws_manager.broadcast(
            session_id,
            {
                "type": "session_update",
                "status": session.status,
                "progress": float(session.progress),
                "final_answer": (session.extra_params or {}).get("final_answer"),
                "error": session.error_message,
            },
        )
        return await self._build_session_response(db, session)

    async def export_session_audit_logs(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
    ) -> list[dict[str, Any]]:
        """导出群聊会话相关审计日志。"""
        stmt = (
            select(AuditLog)
            .where(
                AuditLog.tenant_id == tenant_id,
                AuditLog.resource_type == "group_chat_session",
                AuditLog.resource_id == session_id,
            )
            .order_by(AuditLog.id)
        )
        rows = (await db.execute(stmt)).scalars().all()
        return [
            {
                "id": row.id,
                "action": row.action,
                "user_id": row.user_id,
                "detail": row.detail,
                "created_at": row.created_at.isoformat() if row.created_at else None,
            }
            for row in rows
        ]

    async def _build_session_response(
        self, db: AsyncSession, session: GroupChatSession
    ) -> GroupChatSessionResponse:
        """刷新 ORM 字段后构建响应，避免 async 下惰性加载 updated_at 报错。"""
        await db.refresh(session)
        return self._to_session_response(session)

    @staticmethod
    def _build_summary_from_session(session: GroupChatSession) -> str:
        """从会话交付物生成最终摘要。"""
        parts = [f"# {session.title}\n\n{session.task_description}\n"]
        for item in session.deliverables or []:
            role = item.get("role", "成员")
            parts.append(f"\n## {role}\n{item.get('content', '')}")
        review = session.review_result or {}
        if review:
            parts.append(f"\n\n**审核说明**：{review.get('summary', '')}")
        return "\n".join(parts)

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

        team_config_holder: dict[str, Any] = {}

        def member_status_callback(role: str, status: str) -> None:
            member_statuses[role] = status
            asyncio.run_coroutine_threadsafe(
                group_chat_ws_manager.broadcast(
                    session_id,
                    {
                        "type": "member_status",
                        "role": role,
                        "status": status,
                        "members": GroupChatEngine.get_members(
                            member_statuses,
                            team_config=team_config_holder.get("config"),
                            subtasks=team_config_holder.get("subtasks"),
                            session_status=team_config_holder.get("status", "running"),
                            review_count=team_config_holder.get("review_count", 0),
                            reject_info=team_config_holder.get("reject_info"),
                        ),
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

            async with async_session_factory() as db:
                stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
                cfg_session = (await db.execute(stmt)).scalar_one()
                team_config = (cfg_session.extra_params or {}).get("team_config") or {}

            team_config_holder["config"] = team_config
            team_config_holder["status"] = "running"
            team_config_holder["subtasks"] = []
            team_config_holder["review_count"] = 0

            engine = GroupChatEngine(
                settings.redis_url, user_ctx=user_ctx, team_config=team_config
            )
            engine.set_team_config(team_config)
            engine.set_execution_context(tenant_id, user_id, session_id)
            engine.set_message_callback(message_callback)
            engine.set_member_status_callback(member_status_callback)

            supplement_bridge = _SupplementBridge()
            async with async_session_factory() as db:
                stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
                boot_session = (await db.execute(stmt)).scalar_one()
                boot_sups = list(
                    (boot_session.extra_params or {}).get("user_supplements") or []
                )
            supplement_bridge.push(boot_sups)
            engine.set_supplement_loader(supplement_bridge.drain)

            stop_poll = asyncio.Event()
            last_supplement_count = len(boot_sups)

            async def poll_user_supplements() -> None:
                nonlocal last_supplement_count
                from app.core.database import async_session_factory as session_factory

                while not stop_poll.is_set():
                    try:
                        async with session_factory() as db:
                            if await self.is_session_cancelled_db(db, session_id):
                                _cancelled_sessions.add(session_id)
                                break
                            stmt = select(GroupChatSession).where(
                                GroupChatSession.id == session_id
                            )
                            row = (await db.execute(stmt)).scalar_one_or_none()
                            if row is None:
                                break
                            sups = list(
                                (row.extra_params or {}).get("user_supplements") or []
                            )
                            if len(sups) > last_supplement_count:
                                supplement_bridge.push(sups[last_supplement_count:])
                                last_supplement_count = len(sups)
                    except Exception as poll_exc:
                        logger.warning(
                            "群聊补充轮询异常 session_id=%s: %s",
                            session_id,
                            poll_exc,
                        )
                    await asyncio.sleep(1)

            poll_task = asyncio.create_task(poll_user_supplements())

            graph = engine.build_graph()
            initial_state: dict[str, Any] = {
                "messages": [],
                "task": task,
                "kb_id": kb_id,
                "team_config": team_config,
                "subtasks": [],
                "results": {},
                "deliverables": [],
                "current_step": "group_chat",
                "status": "running",
                "error": "",
                "require_human_approval": False,
                "human_approved": False,
                "execution_logs": [],
                "loop_counters": {},
                "progress": 0.0,
                "current_subtask_index": 0,
                "review_count": 0,
                "review_result": None,
                "user_supplements": [],
                "final_answer": "",
                "tenant_id": tenant_id,
                "user_id": user_id,
                "current_phase": 1,
                "workflow_phases": team_config.get("workflow_phases") or [],
            }
            config = {
                "configurable": {"thread_id": thread_id},
                "recursion_limit": 120,
            }

            if self.is_session_cancelled(session_id):
                await self._mark_session_failed(session_id, "会话已被用户取消")
                stop_poll.set()
                await poll_task
                return

            loop = asyncio.get_event_loop()
            final_state = dict(initial_state)

            def _stream_graph() -> dict[str, Any]:
                state = dict(initial_state)
                for chunk in graph.stream(state, config):
                    if session_id in _cancelled_sessions:
                        state["status"] = "cancelled"
                        state["error"] = "用户已取消协作"
                        break
                    for _, node_state in chunk.items():
                        if isinstance(node_state, dict):
                            state.update(node_state)
                return state

            try:
                final_state = await asyncio.wait_for(
                    loop.run_in_executor(None, _stream_graph),
                    timeout=settings.workflow_execution_timeout_seconds,
                )
            finally:
                stop_poll.set()
                await poll_task

            if self.is_session_cancelled(session_id) or final_state.get("status") == "cancelled":
                await self._mark_session_failed(session_id, "用户已取消协作")
                return

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

        started_at: Optional[datetime] = None
        async with async_session_factory() as db:
            stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
            session = (await db.execute(stmt)).scalar_one()
            started_at = session.created_at
            session.status = final_state.get("status", "completed")
            session.progress = float(final_state.get("progress", 100.0))
            session.subtasks = final_state.get("subtasks", [])
            session.deliverables = final_state.get("deliverables", [])
            session.review_result = final_state.get("review_result")
            session.review_count = int(final_state.get("review_count") or 0)
            session.error_message = final_state.get("error") or None
            ppt_file = final_state.get("ppt_file")
            if ppt_file:
                extra = dict(session.extra_params or {})
                extra["ppt_file"] = ppt_file
                extra["final_answer"] = final_state.get("final_answer")
                session.extra_params = extra
            elif final_state.get("final_answer"):
                extra = dict(session.extra_params or {})
                extra["final_answer"] = final_state.get("final_answer")
                session.extra_params = extra
            if session.status in ("completed", "failed", "human_review"):
                session.completed_at = datetime.now(timezone.utc)
            duration_ms = None
            if started_at and session.completed_at:
                duration_ms = (
                    session.completed_at - started_at
                ).total_seconds() * 1000
            status = session.status
            review_passed = None
            if status == "completed":
                review_passed = True
            elif status == "failed":
                review_passed = False
            event = status if status in ("completed", "failed", "human_review") else "completed"
            await monitor_service.record_group_chat_event(
                event,
                duration_ms=duration_ms,
                review_passed=review_passed,
                review_retries=int(final_state.get("review_count") or 0),
            )
            await audit_service.record_action(
                db=db,
                tenant_id=session.tenant_id,
                user_id=session.user_id,
                action=f"group_chat.session_{event}",
                resource_type="group_chat_session",
                resource_id=session_id,
                detail={
                    "review_count": final_state.get("review_count"),
                    "progress": float(session.progress),
                },
            )
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
        """标记会话失败（中文错误说明）。"""
        from app.core.database import async_session_factory

        facing = translate_error_message(
            error,
            context={"execution_id": session_id},
        )
        user_message = facing.user_message
        suggestions = [s.to_dict() for s in facing.suggestions]

        async with async_session_factory() as db:
            stmt = select(GroupChatSession).where(GroupChatSession.id == session_id)
            session = (await db.execute(stmt)).scalar_one_or_none()
            if session is None:
                return
            session.status = "failed"
            session.error_message = user_message
            extra = dict(session.extra_params or {})
            extra["error_code"] = facing.error_code
            extra["error_suggestions"] = suggestions
            extra["raw_error"] = facing.raw_error
            session.extra_params = extra
            session.completed_at = datetime.now(timezone.utc)
            await db.commit()

        await group_chat_ws_manager.broadcast(
            session_id,
            {
                "type": "session_update",
                "status": "failed",
                "error": user_message,
                "error_code": facing.error_code,
                "error_suggestions": suggestions,
                "raw_error": facing.raw_error,
            },
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

    async def get_deliverable_file(
        self,
        db: AsyncSession,
        session_id: int,
        tenant_id: int,
        filename: str,
    ) -> tuple[str, str]:
        """获取群聊交付物文件路径（租户隔离校验）。"""
        from app.services.delivery.ppt_generator_service import ppt_generator_service

        await self._get_session_or_raise(db, session_id, tenant_id)
        file_path = ppt_generator_service.get_file_path(tenant_id, session_id, filename)
        if file_path is None:
            raise NotFoundError(message="交付物文件不存在")
        return str(file_path), filename

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
        extra = session.extra_params or {}
        member_statuses = extra.get("member_statuses") or {}
        team_config = extra.get("team_config")
        reject_info = extra.get("reject_info") or {}
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
            error_code=extra.get("error_code"),
            error_suggestions=extra.get("error_suggestions") or [],
            raw_error=extra.get("raw_error"),
            completed_at=session.completed_at,
            created_at=session.created_at,
            updated_at=session.updated_at,
            members=[
                GroupChatMemberInfo(**m)
                for m in GroupChatEngine.get_members(
                    member_statuses,
                    team_config=team_config,
                    subtasks=session.subtasks or [],
                    session_status=session.status,
                    review_count=session.review_count,
                    reject_info=reject_info,
                )
            ],
            progress_steps=[
                GroupChatProgressStep(**s)
                for s in GroupChatEngine.get_progress_steps(
                    session.status,
                    session.subtasks or [],
                    team_config=team_config,
                )
            ],
            team_config=team_config,
        )

    def _to_session_detail_response(
        self, session: GroupChatSession
    ) -> GroupChatSessionDetailResponse:
        """转换为含消息的会话详情响应。"""
        base = self._to_session_response(session)
        messages = [
            GroupChatMessageResponse(
                id=msg.id,
                message_id=msg.message_id,
                sender_role=msg.sender_role,
                message_type=msg.message_type,
                content=msg.content,
                payload=msg.payload or {},
                created_at=msg.created_at,
            )
            for msg in (session.messages or [])
        ]
        return GroupChatSessionDetailResponse(**base.model_dump(), messages=messages)


group_chat_service = GroupChatService()
