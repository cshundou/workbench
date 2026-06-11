"""
知识库检索工具：对接增强 RAG 系统。
"""

from typing import Any, Dict, Optional

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.knowledge_base import KnowledgeBase
from app.models.user import User
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.rag.rag_service import rag_service
from app.services.user_key_context import UserKeyContext

logger = get_logger(__name__)


class KnowledgeBaseTool(BaseTool):
    """搜索企业私有知识库。"""

    name = "knowledge_base_search"
    description = "搜索企业私有知识库中的信息，用于回答与企业内部文档相关的问题"
    parameters = {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "要搜索的问题",
            },
            "kb_id": {
                "type": "integer",
                "description": "知识库ID，可选，不指定则搜索所有有权限的知识库",
            },
        },
        "required": ["query"],
    }

    def __init__(
        self,
        db: AsyncSession,
        tenant_id: int,
        user: User,
        user_ctx: UserKeyContext,
    ) -> None:
        self.db = db
        self.tenant_id = tenant_id
        self.user = user
        self.user_ctx = user_ctx

    async def _list_accessible_kb_ids(self, kb_id: Optional[int] = None) -> list[int]:
        """获取当前用户可访问的知识库 ID 列表。"""
        stmt = select(KnowledgeBase.id).where(
            KnowledgeBase.tenant_id == self.tenant_id,
            KnowledgeBase.status == 1,
            or_(
                KnowledgeBase.is_public.is_(True),
                KnowledgeBase.owner_id == self.user.id,
            ),
        )
        if kb_id is not None:
            stmt = stmt.where(KnowledgeBase.id == kb_id)

        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def execute(self, parameters: Dict[str, Any]) -> ToolResult:
        """执行知识库混合检索。"""
        try:
            query = parameters["query"]
            kb_id = parameters.get("kb_id")
            accessible_ids = await self._list_accessible_kb_ids(kb_id)

            if not accessible_ids:
                return ToolResult(
                    success=False,
                    content=None,
                    error="无可访问的知识库或指定知识库不存在",
                )

            all_results: list[dict[str, Any]] = []
            for current_kb_id in accessible_ids:
                try:
                    results = await rag_service.retrieve(
                        self.db,
                        current_kb_id,
                        query,
                        self.user_ctx,
                        top_k=5,
                    )
                    for item in results:
                        metadata = item.get("metadata", {})
                        all_results.append(
                            {
                                "content": item.get("content", ""),
                                "source": metadata.get("document_name", "未知文档"),
                                "kb_id": current_kb_id,
                                "score": item.get("score"),
                            }
                        )
                except Exception as exc:
                    logger.warning(
                        "知识库检索失败 kb_id=%s error=%s",
                        current_kb_id,
                        exc,
                    )

            return ToolResult(
                success=True,
                content={"results": all_results[:10]},
            )
        except Exception as exc:
            logger.error("KnowledgeBaseTool 执行失败: %s", exc)
            return ToolResult(
                success=False,
                content=None,
                error=str(exc),
            )
