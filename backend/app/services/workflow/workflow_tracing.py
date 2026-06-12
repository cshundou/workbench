"""
工作流同步执行链路追踪（节点 Span 记录）。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


def _run_async(coro: Any) -> None:
    """在同步 LangGraph 节点中执行异步 Span 写入。"""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                pool.submit(asyncio.run, coro).result()
        else:
            asyncio.run(coro)
    except Exception as exc:
        logger.debug("Span 记录失败: %s", exc)


async def _record_span_async(
    trace_id: str,
    tenant_id: int,
    name: str,
    kind: str,
    *,
    status: str = "ok",
    input_data: Optional[dict[str, Any]] = None,
    output_data: Optional[dict[str, Any]] = None,
    error_message: Optional[str] = None,
    duration_ms: Optional[int] = None,
) -> None:
    from app.core.database import async_session_factory
    from app.services.trace.trace_service import trace_service

    async with async_session_factory() as db:
        await trace_service.add_span(
            db,
            trace_id=trace_id,
            name=name,
            kind=kind,
            input_data=input_data,
            output_data=output_data,
            error_message=error_message,
            duration_ms=duration_ms,
            status=status,
        )
        await db.commit()


def record_workflow_node_span(
    trace_id: Optional[str],
    tenant_id: Optional[int],
    node_id: str,
    status: str,
    log_data: Optional[dict[str, Any]] = None,
) -> None:
    """记录工作流节点 Span（供 WorkflowBuilder 同步调用）。"""
    if not trace_id or tenant_id is None:
        return
    span_status = "error" if status == "failed" else "ok"
    _run_async(
        _record_span_async(
            trace_id,
            tenant_id,
            name=f"workflow.node.{node_id}",
            kind="node",
            status=span_status,
            input_data=(log_data or {}).get("input_data"),
            output_data=(log_data or {}).get("output_data"),
            error_message=(log_data or {}).get("error"),
        )
    )


def record_tool_span(
    trace_id: Optional[str],
    tenant_id: Optional[int],
    tool_name: str,
    *,
    success: bool,
    duration_ms: Optional[int] = None,
) -> None:
    """记录工具调用 Span。"""
    if not trace_id or tenant_id is None:
        return
    _run_async(
        _record_span_async(
            trace_id,
            tenant_id,
            name=f"tool.{tool_name}",
            kind="tool",
            status="ok" if success else "error",
            duration_ms=duration_ms,
        )
    )
