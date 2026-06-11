"""
工作流业务服务：CRUD、执行调度、人工介入与状态管理。
"""

import asyncio
import logging
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.guardrails import guardrails_service
from app.core.task_queue import enqueue_task
from app.models.user import User
from app.models.workflow import Workflow
from app.models.workflow_execution import WorkflowExecution
from app.schemas.workflow import (
    HumanInterventionRequest,
    NodeExecutionLog,
    WorkflowCreate,
    WorkflowExecutionListResponse,
    WorkflowExecutionResponse,
    WorkflowExecuteRequest,
    WorkflowListResponse,
    WorkflowResponse,
    WorkflowUpdate,
)
from app.services.workflow.graph_builder import (
    NODE_LABELS,
    STANDARD_GRAPH_DEFINITION,
    WorkflowBuilder,
)
from app.services.user_key_context import user_key_resolver
from app.services.workflow.ws_manager import workflow_ws_manager
from app.services.audit_service import audit_service

logger = logging.getLogger(__name__)

# 内存中维护执行运行时状态（节点状态、日志），与 Redis 检查点互补
_runtime_state: dict[int, dict[str, Any]] = {}
# 用户主动终止的执行 ID 集合
_cancelled_executions: set[int] = set()


class WorkflowService:
    """工作流 CRUD 与执行业务逻辑。"""

    def _to_workflow_response(self, workflow: Workflow) -> WorkflowResponse:
        return WorkflowResponse(
            id=workflow.id,
            tenant_id=workflow.tenant_id,
            name=workflow.name,
            description=workflow.description,
            graph_definition=workflow.graph_definition,
            owner_id=workflow.owner_id,
            is_public=workflow.is_public,
            status=workflow.status,
            published_at=workflow.published_at,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    def _to_execution_response(
        self,
        execution: WorkflowExecution,
        include_runtime: bool = True,
    ) -> WorkflowExecutionResponse:
        runtime = _runtime_state.get(execution.id, {}) if include_runtime else {}
        logs_raw = runtime.get("logs") or list(execution.execution_logs or [])
        node_statuses = runtime.get("node_statuses") or dict(execution.node_statuses or {})
        logs = [NodeExecutionLog(**log) for log in logs_raw]
        return WorkflowExecutionResponse(
            id=execution.id,
            workflow_id=execution.workflow_id,
            tenant_id=execution.tenant_id,
            status=execution.status,
            input_params=execution.input_params,
            output_result=execution.output_result,
            error_message=execution.error_message,
            started_at=execution.started_at,
            completed_at=execution.completed_at,
            created_by=execution.created_by,
            thread_id=runtime.get("thread_id"),
            task_id=runtime.get("task_id"),
            node_statuses=node_statuses,
            logs=logs,
        )

    async def _persist_execution_runtime(
        self,
        execution_id: int,
        logs: list[dict[str, Any]],
        node_statuses: dict[str, str],
    ) -> None:
        """将运行时日志与节点状态持久化到数据库。"""
        from app.core.database import async_session_factory

        try:
            async with async_session_factory() as db:
                stmt = select(WorkflowExecution).where(
                    WorkflowExecution.id == execution_id
                )
                result = await db.execute(stmt)
                execution = result.scalar_one_or_none()
                if execution is None:
                    return
                execution.execution_logs = logs
                execution.node_statuses = node_statuses
                await db.commit()
        except Exception as exc:
            logger.warning(
                "持久化工作流执行日志失败 execution_id=%s: %s",
                execution_id,
                exc,
            )

    async def _get_workflow_or_raise(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
    ) -> Workflow:
        stmt = select(Workflow).where(
            Workflow.id == workflow_id,
            Workflow.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        workflow = result.scalar_one_or_none()
        if workflow is None:
            raise NotFoundError(message="工作流不存在")
        return workflow

    async def _check_workflow_access(
        self,
        workflow: Workflow,
        user: User,
        require_owner: bool = False,
    ) -> None:
        if workflow.is_public and not require_owner:
            return
        if workflow.owner_id == user.id:
            return
        if require_owner:
            raise ValidationError(message="仅工作流所有者可执行此操作")
        raise ValidationError(message="无权访问该工作流")

    async def _get_execution_or_raise(
        self,
        db: AsyncSession,
        execution_id: int,
        tenant_id: int,
    ) -> WorkflowExecution:
        stmt = select(WorkflowExecution).where(
            WorkflowExecution.id == execution_id,
            WorkflowExecution.tenant_id == tenant_id,
        )
        result = await db.execute(stmt)
        execution = result.scalar_one_or_none()
        if execution is None:
            raise NotFoundError(message="执行记录不存在")
        return execution

    def _init_runtime_state(self, execution_id: int, thread_id: str) -> None:
        """初始化执行运行时状态。"""
        node_statuses = {node_id: "waiting" for node_id in NODE_LABELS}
        _runtime_state[execution_id] = {
            "thread_id": thread_id,
            "node_statuses": node_statuses,
            "logs": [],
        }

    def _update_node_status(
        self,
        execution_id: int,
        node_id: str,
        status: str,
        log_entry: dict[str, Any],
    ) -> None:
        runtime = _runtime_state.setdefault(
            execution_id,
            {"thread_id": "", "node_statuses": {}, "logs": []},
        )
        runtime["node_statuses"][node_id] = status
        runtime["logs"].append(log_entry)
        running_nodes = [
            nid
            for nid, node_status in runtime["node_statuses"].items()
            if node_status == "running"
        ]
        runtime["parallel_running_nodes"] = running_nodes
        runtime["is_parallel_active"] = len(running_nodes) > 1
        asyncio.create_task(
            self._persist_execution_runtime(
                execution_id,
                list(runtime.get("logs", [])),
                dict(runtime.get("node_statuses", {})),
            )
        )

    async def list_workflows(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> WorkflowListResponse:
        """分页查询工作流列表。"""
        base_filter = or_(
            Workflow.tenant_id == tenant_id,
            Workflow.is_public.is_(True),
        )
        if user.id:
            base_filter = or_(
                base_filter,
                Workflow.owner_id == user.id,
            )

        count_stmt = select(func.count()).select_from(Workflow).where(
            Workflow.tenant_id == tenant_id
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(Workflow)
            .where(Workflow.tenant_id == tenant_id)
            .order_by(Workflow.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = [
            self._to_workflow_response(w) for w in result.scalars().all()
        ]
        return WorkflowListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def create_workflow(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        data: WorkflowCreate,
    ) -> WorkflowResponse:
        """创建工作流模板。"""
        graph_def = (
            data.graph_definition.model_dump()
            if data.graph_definition
            else STANDARD_GRAPH_DEFINITION
        )
        workflow = Workflow(
            tenant_id=tenant_id,
            name=data.name,
            description=data.description,
            graph_definition=graph_def,
            owner_id=user.id,
            is_public=data.is_public,
        )
        db.add(workflow)
        try:
            await db.flush()
            await db.refresh(workflow)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="工作流名称已存在") from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.create",
            resource_type="workflow",
            resource_id=workflow.id,
            detail={"name": workflow.name, "is_public": workflow.is_public},
        )
        logger.info("创建工作流 id=%s name=%s", workflow.id, workflow.name)
        return self._to_workflow_response(workflow)

    async def get_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
    ) -> WorkflowResponse:
        """获取工作流详情。"""
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user)
        return self._to_workflow_response(workflow)

    async def update_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
        data: WorkflowUpdate,
    ) -> WorkflowResponse:
        """更新工作流。"""
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user, require_owner=True)

        if data.name is not None:
            workflow.name = data.name
        if data.description is not None:
            workflow.description = data.description
        if data.graph_definition is not None:
            workflow.graph_definition = data.graph_definition.model_dump()
        if data.is_public is not None:
            workflow.is_public = data.is_public

        try:
            await db.flush()
            await db.refresh(workflow)
        except IntegrityError as exc:
            await db.rollback()
            raise ConflictError(message="工作流名称已存在") from exc

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.update",
            resource_type="workflow",
            resource_id=workflow.id,
            detail=data.model_dump(exclude_unset=True),
        )
        return self._to_workflow_response(workflow)

    async def delete_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
    ) -> None:
        """删除工作流。"""
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user, require_owner=True)
        await db.delete(workflow)
        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.delete",
            resource_type="workflow",
            resource_id=workflow_id,
            detail={"name": workflow.name},
        )
        logger.info("删除工作流 id=%s", workflow_id)

    async def publish_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
    ) -> WorkflowResponse:
        """发布工作流模板（草稿 -> 已发布）。"""
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user, require_owner=True)

        if workflow.status == "published":
            raise ValidationError(message="工作流已发布")

        validation = self.validate_graph_definition(workflow.graph_definition)
        if not validation["valid"]:
            raise ValidationError(
                message="工作流图定义校验失败，无法发布",
                error="; ".join(validation["errors"]),
            )

        workflow.status = "published"
        workflow.published_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(workflow)

        await audit_service.record_crud_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.publish",
            resource_type="workflow",
            resource_id=workflow.id,
            detail={
                "name": workflow.name,
                "success": True,
                "result": "published",
            },
        )
        logger.info("发布工作流 id=%s", workflow_id)
        return self._to_workflow_response(workflow)

    async def list_executions(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
        page: int = 1,
        page_size: int = 20,
    ) -> WorkflowExecutionListResponse:
        """查询工作流执行历史。"""
        await self._get_workflow_or_raise(db, workflow_id, tenant_id)

        count_stmt = (
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.tenant_id == tenant_id,
            )
        )
        total = (await db.execute(count_stmt)).scalar_one()

        stmt = (
            select(WorkflowExecution)
            .where(
                WorkflowExecution.workflow_id == workflow_id,
                WorkflowExecution.tenant_id == tenant_id,
            )
            .order_by(WorkflowExecution.started_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        result = await db.execute(stmt)
        items = [
            self._to_execution_response(e) for e in result.scalars().all()
        ]
        return WorkflowExecutionListResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
        )

    async def get_execution_status(
        self,
        db: AsyncSession,
        execution_id: int,
        tenant_id: int,
    ) -> WorkflowExecutionResponse:
        """获取执行状态与节点日志。"""
        execution = await self._get_execution_or_raise(db, execution_id, tenant_id)
        return self._to_execution_response(execution)

    async def execute_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
        data: WorkflowExecuteRequest,
    ) -> WorkflowExecutionResponse:
        """创建执行记录并异步启动工作流。"""
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user)

        if workflow.status != "published":
            raise ValidationError(message="仅已发布的工作流可以执行")

        await guardrails_service.validate_user_input(data.task)

        input_params = {
            "task": data.task,
            "require_human_approval": data.require_human_approval,
            "kb_id": data.kb_id,
            **data.extra_params,
        }

        execution = WorkflowExecution(
            workflow_id=workflow_id,
            tenant_id=tenant_id,
            status="pending",
            input_params=input_params,
            created_by=user.id,
        )
        db.add(execution)
        await db.flush()
        await db.refresh(execution)

        thread_id = f"execution_{execution.id}"
        self._init_runtime_state(execution.id, thread_id)

        task_id = await enqueue_task(
            "execute_workflow_task",
            execution.id,
            workflow_id,
            tenant_id,
            user.id,
            input_params,
            thread_id,
        )
        _runtime_state.setdefault(execution.id, {})["task_id"] = task_id

        logger.info(
            "启动工作流执行 execution_id=%s workflow_id=%s task_id=%s",
            execution.id,
            workflow_id,
            task_id,
        )
        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.execute",
            resource_type="workflow_execution",
            resource_id=execution.id,
            detail={"workflow_id": workflow_id, "task_id": task_id},
        )
        return self._to_execution_response(execution)

    def is_execution_cancelled(self, execution_id: int) -> bool:
        """检查执行是否已被用户终止。"""
        return execution_id in _cancelled_executions

    async def cancel_execution(
        self,
        db: AsyncSession,
        execution_id: int,
        tenant_id: int,
        user: User,
    ) -> WorkflowExecutionResponse:
        """终止正在执行的工作流并撤销 ARQ 任务。"""
        from app.core.task_queue import revoke_task

        execution = await self._get_execution_or_raise(db, execution_id, tenant_id)

        if execution.status not in ("pending", "running", "interrupted"):
            raise ValidationError(message="当前执行无法终止")

        runtime = _runtime_state.get(execution_id, {})
        task_id = runtime.get("task_id")
        if task_id:
            await revoke_task(task_id)

        _cancelled_executions.add(execution_id)
        execution.status = "failed"
        execution.error_message = "工作流已被用户终止"
        execution.completed_at = datetime.now(timezone.utc)
        await db.flush()

        await workflow_ws_manager.broadcast_execution_status(
            execution_id,
            "failed",
            {"error": execution.error_message, "cancelled": True},
        )
        await audit_service.record_action(
            db=db,
            tenant_id=tenant_id,
            user_id=user.id,
            action="workflow.cancel",
            resource_type="workflow_execution",
            resource_id=execution_id,
            detail={"task_id": task_id},
        )
        logger.info("工作流已终止 execution_id=%s task_id=%s", execution_id, task_id)
        return self._to_execution_response(execution)

    async def handle_human_intervention(
        self,
        db: AsyncSession,
        execution_id: int,
        tenant_id: int,
        data: HumanInterventionRequest,
    ) -> WorkflowExecutionResponse:
        """处理人工介入：批准或拒绝继续执行。"""
        execution = await self._get_execution_or_raise(db, execution_id, tenant_id)

        if execution.status != "interrupted":
            raise ValidationError(message="当前执行不处于等待人工确认状态")

        runtime = _runtime_state.get(execution_id, {})
        thread_id = runtime.get("thread_id", f"execution_{execution_id}")

        if not data.approved:
            execution.status = "failed"
            execution.error_message = data.comment or "人工审批已拒绝"
            execution.completed_at = datetime.now(timezone.utc)
            await db.flush()
            await workflow_ws_manager.broadcast_execution_status(
                execution_id, "failed", {"message": execution.error_message}
            )
            return self._to_execution_response(execution)

        input_params = execution.input_params
        task_id = await enqueue_task(
            "resume_workflow_task",
            execution_id,
            tenant_id,
            input_params,
            thread_id,
            comment=data.comment,
        )
        _runtime_state.setdefault(execution_id, {})["task_id"] = task_id
        return self._to_execution_response(execution)

    async def run_workflow_task(
        self,
        execution_id: int,
        workflow_id: int,
        tenant_id: int,
        user_id: int,
        input_params: dict[str, Any],
        thread_id: str,
    ) -> None:
        """在后台任务中执行 LangGraph 工作流。"""
        from app.core.database import async_session_factory

        def status_callback(
            node_id: str, status: str, log_entry: dict[str, Any]
        ) -> None:
            self._update_node_status(execution_id, node_id, status, log_entry)
            asyncio.create_task(
                workflow_ws_manager.broadcast_node_status(
                    execution_id, node_id, status, log_entry
                )
            )

        try:
            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            user_ctx = None
            graph_definition: dict[str, Any] | None = None
            async with async_session_factory() as db:
                stmt = select(WorkflowExecution).where(
                    WorkflowExecution.id == execution_id
                )
                result = await db.execute(stmt)
                execution = result.scalar_one()
                execution.status = "running"

                wf_stmt = select(Workflow).where(Workflow.id == workflow_id)
                workflow = (await db.execute(wf_stmt)).scalar_one()
                graph_definition = workflow.graph_definition

                user_ctx = await user_key_resolver.load_context(
                    db, user_id, tenant_id
                )
                await db.commit()

            await workflow_ws_manager.broadcast_execution_status(
                execution_id, "running"
            )

            require_human = bool(input_params.get("require_human_approval"))
            builder = WorkflowBuilder(settings.redis_url, user_ctx=user_ctx)
            builder.set_status_callback(status_callback)
            graph = builder.build_workflow(graph_definition, require_human=require_human)

            initial_state = {
                "messages": [],
                "task": input_params.get("task", ""),
                "subtasks": [],
                "results": {},
                "current_step": "init",
                "status": "running",
                "error": "",
                "require_human_approval": require_human,
                "human_approved": False,
                "kb_id": input_params.get("kb_id"),
                "execution_logs": [],
            }

            config = {"configurable": {"thread_id": thread_id}}

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                None,
                lambda: graph.invoke(initial_state, config),
            )

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            await self._finalize_execution(
                execution_id, final_state, require_human
            )
        except asyncio.CancelledError:
            logger.info("工作流任务已撤销 execution_id=%s", execution_id)
            await self._mark_execution_failed(execution_id, "工作流已被用户终止")
        except Exception as exc:
            logger.exception("工作流执行失败 execution_id=%s: %s", execution_id, exc)
            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
            else:
                await self._mark_execution_failed(execution_id, str(exc))

    async def run_resume_workflow_task(
        self,
        execution_id: int,
        tenant_id: int,
        input_params: dict[str, Any],
        thread_id: str,
        comment: Optional[str],
    ) -> None:
        """人工批准后恢复工作流执行。"""
        def status_callback(
            node_id: str, status: str, log_entry: dict[str, Any]
        ) -> None:
            self._update_node_status(execution_id, node_id, status, log_entry)
            asyncio.create_task(
                workflow_ws_manager.broadcast_node_status(
                    execution_id, node_id, status, log_entry
                )
            )

        try:
            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                stmt = select(WorkflowExecution).where(
                    WorkflowExecution.id == execution_id,
                    WorkflowExecution.tenant_id == tenant_id,
                )
                result = await db.execute(stmt)
                execution = result.scalar_one()
                execution.status = "running"

                wf_stmt = select(Workflow).where(
                    Workflow.id == execution.workflow_id
                )
                workflow = (await db.execute(wf_stmt)).scalar_one()
                graph_definition = workflow.graph_definition

                user_ctx = await user_key_resolver.load_context(
                    db, execution.created_by, tenant_id
                )
                await db.commit()

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            require_human = bool(input_params.get("require_human_approval"))
            builder = WorkflowBuilder(settings.redis_url, user_ctx=user_ctx)
            builder.set_status_callback(status_callback)
            graph = builder.build_workflow(graph_definition, require_human=require_human)

            resume_state = {
                "human_approved": True,
                "status": "running",
            }
            if comment:
                resume_state["results"] = {"human_comment": comment}

            config = {"configurable": {"thread_id": thread_id}}
            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                None,
                lambda: graph.invoke(resume_state, config),
            )

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            await self._finalize_execution(
                execution_id, final_state, require_human
            )
        except asyncio.CancelledError:
            logger.info("工作流恢复任务已撤销 execution_id=%s", execution_id)
            await self._mark_execution_failed(execution_id, "工作流已被用户终止")
        except Exception as exc:
            logger.exception(
                "工作流恢复失败 execution_id=%s: %s", execution_id, exc
            )
            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
            else:
                await self._mark_execution_failed(execution_id, str(exc))

    async def _finalize_execution(
        self,
        execution_id: int,
        final_state: dict[str, Any] | None,
        require_human: bool,
    ) -> None:
        """根据最终状态更新执行记录。"""
        from app.core.database import async_session_factory

        if final_state is None:
            await self._mark_execution_failed(execution_id, "工作流返回空状态")
            return

        status = final_state.get("status", "completed")
        final_status = status
        output_result: dict[str, Any] | None = None

        async with async_session_factory() as db:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            )
            result = await db.execute(stmt)
            execution = result.scalar_one()

            if status == "waiting_for_human" and require_human:
                execution.status = "interrupted"
                execution.output_result = {
                    "results": final_state.get("results", {}),
                    "current_step": final_state.get("current_step"),
                }
                await db.commit()
                await workflow_ws_manager.broadcast_execution_status(
                    execution_id,
                    "interrupted",
                    {"message": "等待人工确认"},
                )
                return

            if status == "failed":
                execution.status = "failed"
                execution.error_message = final_state.get("error", "执行失败")
                execution.completed_at = datetime.now(timezone.utc)
                final_status = "failed"
                output_result = None
            else:
                execution.status = "completed"
                output_result = {
                    "results": final_state.get("results", {}),
                    "final": final_state.get("results", {}).get("final"),
                }
                execution.output_result = output_result
                execution.completed_at = datetime.now(timezone.utc)
                final_status = "completed"

            await db.commit()

        await workflow_ws_manager.broadcast_execution_status(
            execution_id,
            final_status,
            output_result,
        )

    async def _mark_execution_failed(
        self, execution_id: int, error_message: str
    ) -> None:
        """标记执行失败。"""
        from app.core.database import async_session_factory

        async with async_session_factory() as db:
            stmt = select(WorkflowExecution).where(
                WorkflowExecution.id == execution_id
            )
            result = await db.execute(stmt)
            execution = result.scalar_one()
            execution.status = "failed"
            execution.error_message = error_message
            execution.completed_at = datetime.now(timezone.utc)
            await db.commit()

        await workflow_ws_manager.broadcast_execution_status(
            execution_id, "failed", {"error": error_message}
        )


    def validate_graph_definition(self, definition: dict[str, Any]) -> dict[str, Any]:
        """
        校验工作流图定义，返回结构化结果（不抛异常）。

        Returns:
            {"valid": bool, "errors": list[str], "warnings": list[str]}
        """
        builder = WorkflowBuilder()
        warnings: list[str] = []
        for node in definition.get("nodes") or []:
            if node.get("type") == "knowledge":
                config = node.get("config") or {}
                if not config.get("kb_ids"):
                    warnings.append(f"节点 {node.get('id')} 未配置 kb_ids")
        try:
            builder.validate_graph_definition(definition)
            return {"valid": True, "errors": [], "warnings": warnings}
        except ValidationError as exc:
            return {"valid": False, "errors": [exc.message], "warnings": warnings}

    async def get_replay_params(
        self,
        db: AsyncSession,
        workflow_id: int,
        execution_id: int,
        tenant_id: int,
    ) -> dict[str, Any]:
        """获取历史执行的重跑参数与图定义快照。"""
        execution = await self._get_execution_or_raise(db, execution_id, tenant_id)
        if execution.workflow_id != workflow_id:
            raise NotFoundError(message="执行记录不存在")
        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        return {
            "execution_id": execution.id,
            "input_params": execution.input_params,
            "graph_definition_snapshot": workflow.graph_definition,
        }


workflow_service = WorkflowService()
