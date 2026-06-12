"""
全链路追踪服务（TraceID / SpanID / CheckpointID）。
"""

import logging
import uuid
from contextlib import asynccontextmanager
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Any, AsyncGenerator, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.execution_trace import ExecutionTrace, TraceSpan

logger = logging.getLogger(__name__)

_current_trace_id: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_current_span_id: ContextVar[Optional[str]] = ContextVar("span_id", default=None)


class TraceService:
    """TraceID 全链路追踪。"""

    @staticmethod
    def generate_trace_id() -> str:
        """生成全局 TraceID。"""
        return f"tr_{uuid.uuid4().hex}"

    @staticmethod
    def generate_span_id() -> str:
        """生成 SpanID。"""
        return f"sp_{uuid.uuid4().hex[:16]}"

    @property
    def current_trace_id(self) -> Optional[str]:
        """当前上下文 TraceID。"""
        return _current_trace_id.get()

    def set_trace_context(
        self, trace_id: str, span_id: Optional[str] = None
    ) -> None:
        """设置当前追踪上下文。"""
        _current_trace_id.set(trace_id)
        if span_id:
            _current_span_id.set(span_id)

    async def start_trace(
        self,
        db: AsyncSession,
        *,
        tenant_id: int,
        user_id: Optional[int],
        resource_type: str,
        resource_id: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
        trace_id: Optional[str] = None,
    ) -> ExecutionTrace:
        """创建追踪根记录。"""
        tid = trace_id or self.generate_trace_id()
        record = ExecutionTrace(
            trace_id=tid,
            tenant_id=tenant_id,
            user_id=user_id,
            resource_type=resource_type,
            resource_id=resource_id,
            status="running",
            started_at=datetime.now(timezone.utc),
            metadata_=metadata or {},
        )
        db.add(record)
        await db.flush()
        self.set_trace_context(tid)
        return record

    async def complete_trace(
        self,
        db: AsyncSession,
        trace_id: str,
        status: str = "completed",
    ) -> None:
        """完成追踪根记录。"""
        stmt = select(ExecutionTrace).where(ExecutionTrace.trace_id == trace_id)
        record = (await db.execute(stmt)).scalar_one_or_none()
        if record is None:
            return
        record.status = status
        record.completed_at = datetime.now(timezone.utc)

    async def add_span(
        self,
        db: AsyncSession,
        *,
        trace_id: str,
        name: str,
        kind: str,
        parent_span_id: Optional[str] = None,
        input_data: Optional[dict[str, Any]] = None,
        output_data: Optional[dict[str, Any]] = None,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None,
        status: str = "ok",
    ) -> TraceSpan:
        """记录 Span。"""
        span_id = self.generate_span_id()
        now = datetime.now(timezone.utc)
        span = TraceSpan(
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id or _current_span_id.get(),
            name=name,
            kind=kind,
            status=status,
            input_data=input_data,
            output_data=output_data,
            error_message=error_message,
            duration_ms=duration_ms,
            started_at=now,
            completed_at=now,
        )
        db.add(span)
        await db.flush()
        return span

    async def get_trace_tree(
        self, db: AsyncSession, trace_id: str, tenant_id: int
    ) -> dict[str, Any]:
        """获取完整调用树。"""
        trace_stmt = select(ExecutionTrace).where(
            ExecutionTrace.trace_id == trace_id,
            ExecutionTrace.tenant_id == tenant_id,
        )
        trace = (await db.execute(trace_stmt)).scalar_one_or_none()
        if trace is None:
            return {}

        spans_stmt = (
            select(TraceSpan)
            .where(TraceSpan.trace_id == trace_id)
            .order_by(TraceSpan.started_at.asc())
        )
        spans = list((await db.execute(spans_stmt)).scalars().all())
        return {
            "trace_id": trace.trace_id,
            "resource_type": trace.resource_type,
            "resource_id": trace.resource_id,
            "status": trace.status,
            "started_at": trace.started_at.isoformat() if trace.started_at else None,
            "completed_at": trace.completed_at.isoformat() if trace.completed_at else None,
            "spans": [
                {
                    "span_id": s.span_id,
                    "parent_span_id": s.parent_span_id,
                    "name": s.name,
                    "kind": s.kind,
                    "status": s.status,
                    "duration_ms": s.duration_ms,
                    "input": s.input_data,
                    "output": s.output_data,
                    "error": s.error_message,
                }
                for s in spans
            ],
        }

    @asynccontextmanager
    async def span(
        self,
        db: AsyncSession,
        *,
        trace_id: str,
        name: str,
        kind: str,
        input_data: Optional[dict[str, Any]] = None,
    ) -> AsyncGenerator[str, None]:
        """Span 上下文管理器，自动记录耗时。"""
        span_id = self.generate_span_id()
        parent = _current_span_id.get()
        _current_span_id.set(span_id)
        started = datetime.now(timezone.utc)
        error_msg: Optional[str] = None
        output: Optional[dict[str, Any]] = None
        status = "ok"
        try:
            yield span_id
        except Exception as exc:
            status = "error"
            error_msg = str(exc)
            raise
        finally:
            duration_ms = int(
                (datetime.now(timezone.utc) - started).total_seconds() * 1000
            )
            await self.add_span(
                db,
                trace_id=trace_id,
                name=name,
                kind=kind,
                parent_span_id=parent,
                input_data=input_data,
                output_data=output,
                error_message=error_msg,
                duration_ms=duration_ms,
                status=status,
            )
            _current_span_id.set(parent)


trace_service = TraceService()
