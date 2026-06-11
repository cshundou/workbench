"""
Token 消耗记录服务。

供 RAG、Agent 等大模型调用链路统一写入 token_usage 表。
"""

from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.token_usage import TokenUsage
from app.services.token_quota_service import token_quota_service

logger = get_logger(__name__)


def extract_token_usage_from_response(response: Any) -> dict[str, int]:
    """
    从 LangChain 模型响应中提取 Token 用量。

    Args:
        response: LangChain AIMessage 或含 usage_metadata 的对象。

    Returns:
        含 prompt_tokens、completion_tokens、total_tokens 的字典。
    """
    prompt_tokens = 0
    completion_tokens = 0
    total_tokens = 0

    usage_metadata = getattr(response, "usage_metadata", None)
    if isinstance(usage_metadata, dict):
        prompt_tokens = int(usage_metadata.get("input_tokens", 0) or 0)
        completion_tokens = int(usage_metadata.get("output_tokens", 0) or 0)
        total_tokens = int(usage_metadata.get("total_tokens", 0) or 0)

    response_metadata = getattr(response, "response_metadata", None)
    if isinstance(response_metadata, dict):
        token_usage = response_metadata.get("token_usage") or response_metadata.get("usage")
        if isinstance(token_usage, dict):
            prompt_tokens = int(
                token_usage.get("prompt_tokens", token_usage.get("input_tokens", prompt_tokens))
                or prompt_tokens
            )
            completion_tokens = int(
                token_usage.get(
                    "completion_tokens",
                    token_usage.get("output_tokens", completion_tokens),
                )
                or completion_tokens
            )
            total_tokens = int(token_usage.get("total_tokens", total_tokens) or total_tokens)

    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": total_tokens,
    }


class TokenUsageService:
    """Token 消耗持久化服务。"""

    async def record_usage(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: Optional[int],
        model_name: str,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: Optional[int] = None,
    ) -> None:
        """
        写入一条 Token 消耗记录。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            user_id: 用户 ID，系统任务可为 None。
            model_name: 模型名称。
            prompt_tokens: 输入 Token 数。
            completion_tokens: 输出 Token 数。
            total_tokens: 总 Token 数，默认两者之和。
        """
        if total_tokens is None:
            total_tokens = prompt_tokens + completion_tokens

        if total_tokens <= 0:
            return

        record = TokenUsage(
            tenant_id=tenant_id,
            user_id=user_id,
            model_name=model_name,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=total_tokens,
        )
        db.add(record)
        await db.flush()
        await token_quota_service.add_usage(tenant_id, total_tokens)
        logger.info(
            "记录 Token 消耗 tenant=%s user=%s model=%s total=%s",
            tenant_id,
            user_id,
            model_name,
            total_tokens,
        )

    async def record_from_langchain_response(
        self,
        db: AsyncSession,
        tenant_id: int,
        user_id: Optional[int],
        model_name: str,
        response: Any,
    ) -> None:
        """
        从 LangChain 响应对象解析并记录 Token 用量。

        Args:
            db: 数据库会话。
            tenant_id: 租户 ID。
            user_id: 用户 ID。
            model_name: 模型名称。
            response: LangChain 模型响应。
        """
        usage = extract_token_usage_from_response(response)
        await self.record_usage(
            db=db,
            tenant_id=tenant_id,
            user_id=user_id,
            model_name=model_name,
            prompt_tokens=usage["prompt_tokens"],
            completion_tokens=usage["completion_tokens"],
            total_tokens=usage["total_tokens"],
        )


token_usage_service = TokenUsageService()
