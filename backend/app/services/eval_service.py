"""
AI 效果评估服务。

封装 RAG 离线评估与 Agent 运行时指标聚合。
"""

import logging
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.redis import get_redis
from app.models.workflow_execution import WorkflowExecution
from app.services.monitor_service import monitor_service

logger = logging.getLogger(__name__)


class EvalService:
    """AI 效果评估。"""

    async def get_rag_eval_summary(self) -> dict[str, Any]:
        """
        返回 RAG 评估指标摘要。

        基于 tests/eval 标准测试集离线结果（Redis 缓存或默认值）。
        """
        try:
            redis = await get_redis()
            cached = await redis.get("eval:rag:latest")
            if cached:
                import json
                return json.loads(cached)
        except Exception as exc:
            logger.debug("读取 RAG 评估缓存失败: %s", exc)

        return {
            "recall_rate": 0.0,
            "accuracy": 0.0,
            "f1_score": 0.0,
            "avg_latency_ms": 0,
            "sample_count": 0,
            "note": "请运行 tests/eval/rag_eval.py 生成评估数据",
        }

    async def get_agent_eval_summary(self, db: AsyncSession, tenant_id: int) -> dict[str, Any]:
        """聚合 Agent 效果指标。"""
        tool_stats = await monitor_service.get_tool_stats()
        completed_stmt = (
            select(func.count())
            .select_from(WorkflowExecution)
            .where(
                WorkflowExecution.tenant_id == tenant_id,
                WorkflowExecution.status == "completed",
            )
        )
        total_stmt = (
            select(func.count())
            .select_from(WorkflowExecution)
            .where(WorkflowExecution.tenant_id == tenant_id)
        )
        completed = (await db.execute(completed_stmt)).scalar_one()
        total = (await db.execute(total_stmt)).scalar_one()
        completion_rate = round(completed / total, 4) if total else 0.0

        return {
            "tool_success_rate": tool_stats.get("summary", {}).get("success_rate", 1.0),
            "task_completion_rate": completion_rate,
            "avg_tool_calls_per_task": tool_stats.get("summary", {}).get("total_calls", 0),
            "workflow_completed": completed,
            "workflow_total": total,
        }

    async def get_full_eval_report(
        self, db: AsyncSession, tenant_id: int
    ) -> dict[str, Any]:
        """完整评估报告。"""
        rag = await self.get_rag_eval_summary()
        agent = await self.get_agent_eval_summary(db, tenant_id)
        return {
            "rag": rag,
            "agent": agent,
            "generated_at": __import__("datetime").datetime.now(
                __import__("datetime").timezone.utc
            ).isoformat(),
        }


eval_service = EvalService()
