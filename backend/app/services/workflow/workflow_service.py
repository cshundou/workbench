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
from app.services.workflow.ws_manager import workflow_ws_manager

logger = logging.getLogger(__name__)

# 内存中维护执行运行时状态（节点状态、日志），与 Redis 检查点互补
_runtime_state: dict[int, dict[str, Any]] = {}
_running_tasks: dict[int, asyncio.Task[None]] = {}


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
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    def _to_execution_response(
        self,
        execution: WorkflowExecution,
        include_runtime: bool = True,
    ) -> WorkflowExecutionResponse:
        runtime = _runtime_state.get(execution.id, {}) if include_runtime else {}
        logs_raw = runtime.get("logs", [])
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
            node_statuses=runtime.get("node_statuses", {}),
            logs=logs,
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
        logger.info("删除工作流 id=%s", workflow_id)

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

        task = asyncio.create_task(
            self._run_workflow(
                execution.id, workflow_id, tenant_id, input_params, thread_id
            )
        )
        _running_tasks[execution.id] = task

        logger.info(
            "启动工作流执行 execution_id=%s workflow_id=%s",
            execution.id,
            workflow_id,
        )
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
        task = asyncio.create_task(
            self._resume_workflow(
                execution_id,
                tenant_id,
                input_params,
                thread_id,
                data.comment,
            )
        )
        _running_tasks[execution_id] = task
        return self._to_execution_response(execution)

    async def _run_workflow(
        self,
        execution_id: int,
        workflow_id: int,
        tenant_id: int,
        input_params: dict[str, Any],
        thread_id: str,
    ) -> None:
        """在后台线程中执行 LangGraph 工作流。"""
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
            async with async_session_factory() as db:
                stmt = select(WorkflowExecution).where(
                    WorkflowExecution.id == execution_id
                )
                result = await db.execute(stmt)
                execution = result.scalar_one()
                execution.status = "running"
                await db.commit()

            await workflow_ws_manager.broadcast_execution_status(
                execution_id, "running"
            )

            require_human = bool(input_params.get("require_human_approval"))
            builder = WorkflowBuilder(settings.redis_url)
            builder.set_status_callback(status_callback)
            graph = builder.build_standard_workflow(require_human=require_human)

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

            loop = asyncio.get_event_loop()
            final_state = await loop.run_in_executor(
                None,
                lambda: graph.invoke(initial_state, config),
            )

            await self._finalize_execution(
                execution_id, final_state, require_human
            )
        except Exception as exc:
            logger.exception("工作流执行失败 execution_id=%s: %s", execution_id, exc)
            await self._mark_execution_failed(execution_id, str(exc))
        finally:
            _running_tasks.pop(execution_id, None)

    async def _resume_workflow(
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
            from app.core.database import async_session_factory

            async with async_session_factory() as db:
                stmt = select(WorkflowExecution).where(
                    WorkflowExecution.id == execution_id,
                    WorkflowExecution.tenant_id == tenant_id,
                )
                result = await db.execute(stmt)
                execution = result.scalar_one()
                execution.status = "running"
                await db.commit()

            require_human = bool(input_params.get("require_human_approval"))
            builder = WorkflowBuilder(settings.redis_url)
            builder.set_status_callback(status_callback)
            graph = builder.build_standard_workflow(require_human=require_human)

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

            await self._finalize_execution(
                execution_id, final_state, require_human
            )
        except Exception as exc:
            logger.exception(
                "工作流恢复失败 execution_id=%s: %s", execution_id, exc
            )
            await self._mark_execution_failed(execution_id, str(exc))
        finally:
            _running_tasks.pop(execution_id, None)

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


workflow_service = WorkflowService()
