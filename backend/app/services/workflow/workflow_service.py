"""
工作流业务服务：CRUD、执行调度、人工介入与状态管理。
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
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
    GraphDefinition,
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
from app.services.workflow.runtime_state_store import runtime_state_store
from app.services.workflow.workflow_templates import (
    get_workflow_template,
    list_workflow_templates,
)
from app.services.audit_service import audit_service
from app.services.token_quota_service import token_quota_service
from app.services.monitor_service import monitor_service

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
            current_version=workflow.current_version,
            created_at=workflow.created_at,
            updated_at=workflow.updated_at,
        )

    def _load_runtime_state(self, execution_id: int) -> dict[str, Any]:
        """优先从 Redis 读取运行时状态，再回落内存。"""
        redis_state = runtime_state_store.get(execution_id)
        if redis_state:
            _runtime_state[execution_id] = redis_state
            return redis_state
        return _runtime_state.get(execution_id, {})

    def _save_runtime_state(self, execution_id: int, runtime: dict[str, Any]) -> None:
        """同步写入内存与 Redis。"""
        _runtime_state[execution_id] = runtime
        runtime_state_store.save(execution_id, runtime)

    def _to_execution_response(
        self,
        execution: WorkflowExecution,
        include_runtime: bool = True,
    ) -> WorkflowExecutionResponse:
        runtime = self._load_runtime_state(execution.id) if include_runtime else {}
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

    def _init_runtime_state(
        self,
        execution_id: int,
        thread_id: str,
        graph_definition: dict[str, Any] | None = None,
    ) -> None:
        """初始化执行运行时状态。"""
        node_ids = [
            node.get("id")
            for node in (graph_definition or STANDARD_GRAPH_DEFINITION).get("nodes", [])
            if node.get("id")
        ]
        if not node_ids:
            node_ids = list(NODE_LABELS.keys())
        node_statuses = {node_id: "waiting" for node_id in node_ids}
        self._save_runtime_state(
            execution_id,
            {
                "thread_id": thread_id,
                "node_statuses": node_statuses,
                "logs": [],
            },
        )

    def _hydrate_runtime_state_from_execution(self, execution: WorkflowExecution) -> None:
        """当内存态缺失时，从数据库执行记录回填运行时状态。"""
        existing = _runtime_state.get(execution.id)
        if existing and existing.get("logs") and existing.get("node_statuses"):
            return

        persisted_logs = list(execution.execution_logs or [])
        persisted_statuses = dict(execution.node_statuses or {})
        if not persisted_statuses:
            persisted_statuses = {node_id: "waiting" for node_id in NODE_LABELS}

        hydrated = {
            "thread_id": (existing or {}).get("thread_id", f"execution_{execution.id}"),
            "task_id": (existing or {}).get("task_id"),
            "node_statuses": persisted_statuses,
            "logs": persisted_logs,
        }
        self._save_runtime_state(execution.id, hydrated)
        logger.info(
            "已回填工作流运行时状态 execution_id=%s logs=%s nodes=%s",
            execution.id,
            len(persisted_logs),
            len(persisted_statuses),
        )

    def _schedule_coroutine(
        self,
        coro: Any,
        main_loop: Optional[asyncio.AbstractEventLoop],
    ) -> None:
        """从工作流执行线程安全地调度协程到 ARQ 主事件循环。"""
        if main_loop is None or not main_loop.is_running():
            logger.warning("无法调度协程：主事件循环不可用")
            return
        try:
            asyncio.run_coroutine_threadsafe(coro, main_loop)
        except Exception as exc:
            logger.warning("调度协程失败: %s", exc)

    def _update_node_status(
        self,
        execution_id: int,
        node_id: str,
        status: str,
        log_entry: dict[str, Any],
        main_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        runtime = self._load_runtime_state(execution_id)
        if not runtime:
            runtime = {"thread_id": "", "node_statuses": {}, "logs": []}
        runtime["node_statuses"][node_id] = status
        runtime["logs"].append(log_entry)
        running_nodes = [
            nid
            for nid, node_status in runtime["node_statuses"].items()
            if node_status == "running"
        ]
        runtime["parallel_running_nodes"] = running_nodes
        runtime["is_parallel_active"] = len(running_nodes) > 1
        self._save_runtime_state(execution_id, runtime)
        self._schedule_coroutine(
            self._persist_execution_runtime(
                execution_id,
                list(runtime.get("logs", [])),
                dict(runtime.get("node_statuses", {})),
            ),
            main_loop,
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

    @staticmethod
    def _next_semantic_version(current: Optional[str]) -> str:
        """生成下一个语义化版本号。"""
        if not current:
            return "v1.0.0"
        try:
            raw = current.lstrip("v")
            major, minor, patch = [int(part) for part in raw.split(".")]
            return f"v{major}.{minor}.{patch + 1}"
        except (ValueError, TypeError):
            return "v1.0.0"

    async def publish_workflow(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
        user: User,
        change_note: Optional[str] = None,
    ) -> WorkflowResponse:
        """发布工作流模板并创建新版本快照。"""
        from app.models.workflow_version import WorkflowVersion

        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user, require_owner=True)

        validation = self.validate_graph_definition(workflow.graph_definition)
        if not validation["valid"]:
            raise ValidationError(
                message="工作流图定义校验失败，无法发布",
                error="; ".join(validation["errors"]),
            )

        next_version = self._next_semantic_version(workflow.current_version)
        version_record = WorkflowVersion(
            workflow_id=workflow.id,
            version=next_version,
            graph_definition=dict(workflow.graph_definition),
            change_note=change_note,
            published_by=user.id,
            published_at=datetime.now(timezone.utc),
        )
        db.add(version_record)

        workflow.status = "published"
        workflow.published_at = datetime.now(timezone.utc)
        workflow.current_version = next_version
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
                "version": next_version,
                "success": True,
                "result": "published",
            },
        )
        logger.info("发布工作流 id=%s version=%s", workflow_id, next_version)
        return self._to_workflow_response(workflow)

    async def list_workflow_versions(
        self,
        db: AsyncSession,
        workflow_id: int,
        tenant_id: int,
    ) -> list[dict[str, Any]]:
        """查询工作流版本历史。"""
        from app.models.workflow_version import WorkflowVersion

        await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        stmt = (
            select(WorkflowVersion)
            .where(WorkflowVersion.workflow_id == workflow_id)
            .order_by(WorkflowVersion.published_at.desc())
        )
        result = await db.execute(stmt)
        return [
            {
                "id": item.id,
                "version": item.version,
                "change_note": item.change_note,
                "published_by": item.published_by,
                "published_at": item.published_at.isoformat() if item.published_at else None,
            }
            for item in result.scalars().all()
        ]

    async def rollback_workflow_version(
        self,
        db: AsyncSession,
        workflow_id: int,
        version_id: int,
        tenant_id: int,
        user: User,
        change_note: Optional[str] = None,
    ) -> WorkflowResponse:
        """回滚到历史版本（创建新版本，不修改历史）。"""
        from app.models.workflow_version import WorkflowVersion

        workflow = await self._get_workflow_or_raise(db, workflow_id, tenant_id)
        await self._check_workflow_access(workflow, user, require_owner=True)

        stmt = select(WorkflowVersion).where(
            WorkflowVersion.id == version_id,
            WorkflowVersion.workflow_id == workflow_id,
        )
        target = (await db.execute(stmt)).scalar_one_or_none()
        if target is None:
            raise NotFoundError(message="版本不存在")

        workflow.graph_definition = dict(target.graph_definition)
        await db.flush()
        return await self.publish_workflow(
            db,
            workflow_id,
            tenant_id,
            user,
            change_note=change_note or f"回滚自 {target.version}",
        )

    async def export_execution_logs(
        self,
        db: AsyncSession,
        execution_id: int,
        tenant_id: int,
        node_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """导出工作流执行日志为 JSON。"""
        execution = await self._get_execution_or_raise(db, execution_id, tenant_id)
        logs = list(execution.execution_logs or [])
        if node_id:
            logs = [log for log in logs if log.get("node_id") == node_id]
        return {
            "execution_id": execution.id,
            "workflow_id": execution.workflow_id,
            "status": execution.status,
            "logs": logs,
            "exported_at": datetime.now(timezone.utc).isoformat(),
        }

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
        runtime = self._load_runtime_state(execution_id)
        if not runtime or (
            not runtime.get("logs") and not runtime.get("node_statuses")
        ):
            self._hydrate_runtime_state_from_execution(execution)
        return self._to_execution_response(execution)

    async def recover_stale_executions(
        self,
        db: AsyncSession,
        stale_after_minutes: int = 10,
    ) -> int:
        """将长时间处于 running 的执行标记为 interrupted。"""
        if stale_after_minutes <= 0:
            stale_after_minutes = 10

        cutoff = datetime.now(timezone.utc) - timedelta(minutes=stale_after_minutes)
        stmt = select(WorkflowExecution).where(
            WorkflowExecution.status == "running",
            WorkflowExecution.started_at < cutoff,
        )
        result = await db.execute(stmt)
        stale_executions = result.scalars().all()
        if not stale_executions:
            return 0

        for execution in stale_executions:
            execution.status = "interrupted"
            if not execution.error_message:
                execution.error_message = "检测到执行中断，请人工确认后恢复执行"
            self._hydrate_runtime_state_from_execution(execution)

        await db.flush()
        logger.warning(
            "已恢复陈旧工作流执行 stale_count=%s cutoff=%s",
            len(stale_executions),
            cutoff.isoformat(),
        )
        return len(stale_executions)

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
        await token_quota_service.check_tenant_quota(db, tenant_id)

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
        self._init_runtime_state(
            execution.id, thread_id, workflow.graph_definition
        )

        task_id = await enqueue_task(
            "execute_workflow_task",
            execution.id,
            workflow_id,
            tenant_id,
            user.id,
            input_params,
            thread_id,
        )
        runtime = self._load_runtime_state(execution.id)
        runtime["task_id"] = task_id
        self._save_runtime_state(execution.id, runtime)

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

        if execution.status in ("completed", "failed"):
            raise ValidationError(message="已完成或已失败的工作流无法终止")

        if execution.status not in ("pending", "running", "interrupted"):
            raise ValidationError(message="当前执行无法终止")

        runtime = self._load_runtime_state(execution_id)
        thread_id = runtime.get("thread_id", f"execution_{execution_id}")
        task_id = runtime.get("task_id")
        if task_id:
            await revoke_task(task_id)

        # 清理 Redis checkpoint 与运行时状态
        try:
            import redis as sync_redis

            from app.services.workflow.redis_saver import RedisSaver

            redis_client = sync_redis.from_url(settings.redis_url, decode_responses=True)
            RedisSaver(redis_client).delete_checkpoint(thread_id)
        except Exception as exc:
            logger.warning("终止时清理 Redis 检查点失败 execution_id=%s: %s", execution_id, exc)

        _cancelled_executions.add(execution_id)

        node_statuses = dict(runtime.get("node_statuses") or execution.node_statuses or {})
        for node_id, node_status in list(node_statuses.items()):
            if node_status in ("running", "waiting", "pending"):
                node_statuses[node_id] = "failed"
        execution.node_statuses = node_statuses

        execution.status = "interrupted"
        execution.error_message = "工作流已被用户终止"
        execution.completed_at = datetime.now(timezone.utc)
        await db.flush()

        runtime_state_store.delete(execution_id)
        _runtime_state.pop(execution_id, None)

        await workflow_ws_manager.broadcast_execution_status(
            execution_id,
            "interrupted",
            {"error": execution.error_message, "cancelled": True},
        )
        await workflow_ws_manager.disconnect_execution(execution_id)
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

        runtime = self._load_runtime_state(execution_id)
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
        runtime["task_id"] = task_id
        self._save_runtime_state(execution_id, runtime)
        return self._to_execution_response(execution)

    def _build_node_configs(
        self, graph_definition: dict[str, Any] | None
    ) -> dict[str, dict[str, Any]]:
        """从图定义提取 node_id -> config 映射。"""
        configs: dict[str, dict[str, Any]] = {}
        for node in (graph_definition or {}).get("nodes") or []:
            node_id = node.get("id")
            if node_id:
                configs[node_id] = dict(node.get("config") or {})
        return configs

    def _configure_builder(
        self,
        builder: WorkflowBuilder,
        tenant_id: int,
        user_id: int,
        execution_id: int,
        status_callback: Any,
        main_loop: Optional[asyncio.AbstractEventLoop] = None,
    ) -> None:
        """统一配置 WorkflowBuilder 回调与执行上下文。"""
        builder.set_execution_context(tenant_id, user_id, execution_id)
        builder.set_status_callback(status_callback)

        def stream_callback(node_id: str, chunk: str) -> None:
            self._schedule_coroutine(
                workflow_ws_manager.broadcast_node_stream(
                    execution_id, node_id, chunk
                ),
                main_loop,
            )

        builder.set_stream_callback(stream_callback)

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

        started_at = datetime.now(timezone.utc)
        main_loop = asyncio.get_running_loop()

        def status_callback(
            node_id: str, status: str, log_entry: dict[str, Any]
        ) -> None:
            self._update_node_status(
                execution_id, node_id, status, log_entry, main_loop
            )
            self._schedule_coroutine(
                workflow_ws_manager.broadcast_node_status(
                    execution_id, node_id, status, log_entry
                ),
                main_loop,
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
            self._configure_builder(
                builder,
                tenant_id,
                user_id,
                execution_id,
                status_callback,
                main_loop,
            )
            graph = builder.build_workflow(graph_definition, require_human=require_human)

            initial_state: dict[str, Any] = {
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
                "loop_counters": {},
                "replan_count": 0,
                "node_configs": self._build_node_configs(graph_definition),
                "tool_calls": [],
                "tenant_id": tenant_id,
                "user_id": user_id,
            }

            config = {"configurable": {"thread_id": thread_id}}

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            loop = asyncio.get_event_loop()

            def _invoke() -> dict[str, Any]:
                return graph.invoke(initial_state, config)

            final_state = await asyncio.wait_for(
                loop.run_in_executor(None, _invoke),
                timeout=settings.workflow_execution_timeout_seconds,
            )

            if self.is_execution_cancelled(execution_id):
                await self._mark_execution_failed(execution_id, "工作流已被用户终止")
                return

            await self._finalize_execution(
                execution_id, final_state, require_human
            )
            duration_ms = (
                datetime.now(timezone.utc) - started_at
            ).total_seconds() * 1000
            await monitor_service.record_workflow_execution(
                success=final_state.get("status") != "failed",
                duration_ms=duration_ms,
            )
        except asyncio.TimeoutError:
            await self._mark_execution_failed(
                execution_id,
                f"工作流执行超时（{settings.workflow_execution_timeout_seconds}秒）",
            )
            await monitor_service.record_workflow_execution(
                success=False,
                duration_ms=settings.workflow_execution_timeout_seconds * 1000,
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
            await monitor_service.record_workflow_execution(success=False, duration_ms=0)

    async def run_resume_workflow_task(
        self,
        execution_id: int,
        tenant_id: int,
        input_params: dict[str, Any],
        thread_id: str,
        comment: Optional[str],
    ) -> None:
        """人工批准后恢复工作流执行。"""
        main_loop = asyncio.get_running_loop()

        def status_callback(
            node_id: str, status: str, log_entry: dict[str, Any]
        ) -> None:
            self._update_node_status(
                execution_id, node_id, status, log_entry, main_loop
            )
            self._schedule_coroutine(
                workflow_ws_manager.broadcast_node_status(
                    execution_id, node_id, status, log_entry
                ),
                main_loop,
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
            user_id = execution.created_by or 0
            builder = WorkflowBuilder(settings.redis_url, user_ctx=user_ctx)
            self._configure_builder(
                builder,
                tenant_id,
                user_id,
                execution_id,
                status_callback,
                main_loop,
            )
            graph = builder.build_workflow(graph_definition, require_human=require_human)

            resume_update: dict[str, Any] = {
                "human_approved": True,
                "status": "running",
            }
            if comment:
                resume_update["results"] = {"human_comment": comment}

            config = {"configurable": {"thread_id": thread_id}}

            def _resume_invoke() -> dict[str, Any]:
                """从 checkpoint 续跑，避免重复执行已完成节点。"""
                try:
                    if hasattr(graph, "get_state"):
                        snapshot = graph.get_state(config)
                        if snapshot and getattr(snapshot, "values", None):
                            return graph.invoke(resume_update, config)
                except Exception as resume_exc:
                    logger.warning(
                        "checkpoint 恢复失败，回退全量 invoke execution_id=%s: %s",
                        execution_id,
                        resume_exc,
                    )
                return graph.invoke(resume_update, config)

            loop = asyncio.get_event_loop()
            final_state = await asyncio.wait_for(
                loop.run_in_executor(None, _resume_invoke),
                timeout=settings.workflow_execution_timeout_seconds,
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


    async def list_builtin_templates(self) -> list[dict[str, Any]]:
        """返回内置工作流模板列表。"""
        return list_workflow_templates()

    async def create_workflow_from_template(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        template_id: str,
        name: Optional[str] = None,
    ) -> WorkflowResponse:
        """从内置模板创建工作流（仅复制拓扑）。"""
        template = get_workflow_template(template_id)
        if template is None:
            raise NotFoundError(message="工作流模板不存在")

        data = WorkflowCreate(
            name=name or template["name"],
            description=template.get("description"),
            graph_definition=GraphDefinition(**template["graph_definition"]),
            is_public=False,
        )
        return await self.create_workflow(db, tenant_id, user, data)

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
