"""
运行时 LLM 故障自动降级服务。
"""

import time
from dataclasses import dataclass, field
from typing import Any, Optional

from langchain_openai import ChatOpenAI

from app.services.model_provider_service import (
    decode_model_preferences,
    model_provider_service,
)
from app.core.logging import get_logger
from app.services.user_key_context import (
    UserKeyContext,
    create_chat_llm,
    infer_llm_provider_from_model,
)

logger = get_logger(__name__)

# 单模型连续失败阈值与恢复时间（秒）
_MODEL_FAILURE_THRESHOLD = 5
_MODEL_RECOVERY_SECONDS = 600


@dataclass
class ModelFailureState:
    """模型失败计数与不可用标记。"""

    failure_count: int = 0
    unavailable_until: float = 0.0


class LlmFallbackService:
    """LLM 运行时降级与熔断保护。"""

    def __init__(self) -> None:
        self._failure_states: dict[str, ModelFailureState] = {}

    @staticmethod
    def is_fallback_error(exc: Exception) -> bool:
        """判断异常是否应触发模型降级。"""
        message = str(exc).lower()
        keywords = (
            "500",
            "502",
            "503",
            "504",
            "timeout",
            "timed out",
            "rate limit",
            "429",
            "quota",
            "insufficient",
            "401",
            "403",
            "permission",
            "authentication",
        )
        return any(keyword in message for keyword in keywords)

    def _model_key(self, user_id: int, model_name: str) -> str:
        return f"{user_id}:{model_name}"

    def is_model_available(self, user_id: int, model_name: str) -> bool:
        """检查模型是否处于可用状态（未熔断）。"""
        state = self._failure_states.get(self._model_key(user_id, model_name))
        if state is None:
            return True
        if state.unavailable_until and time.time() < state.unavailable_until:
            return False
        if state.unavailable_until and time.time() >= state.unavailable_until:
            state.failure_count = 0
            state.unavailable_until = 0.0
        return True

    def record_failure(self, user_id: int, model_name: str) -> None:
        """记录模型失败并在达到阈值后临时熔断。"""
        key = self._model_key(user_id, model_name)
        state = self._failure_states.setdefault(key, ModelFailureState())
        state.failure_count += 1
        if state.failure_count >= _MODEL_FAILURE_THRESHOLD:
            state.unavailable_until = time.time() + _MODEL_RECOVERY_SECONDS
            logger.warning(
                "模型已临时熔断 model=%s user_id=%s until=%s",
                model_name,
                user_id,
                state.unavailable_until,
            )

    def record_success(self, user_id: int, model_name: str) -> None:
        """成功后重置失败计数。"""
        key = self._model_key(user_id, model_name)
        if key in self._failure_states:
            self._failure_states[key] = ModelFailureState()

    def build_model_priority(
        self,
        user_ctx: UserKeyContext,
        primary_model: str,
        model_priorities: Optional[list[str]] = None,
    ) -> list[str]:
        """构建模型尝试顺序。"""
        ordered: list[str] = []
        if model_priorities:
            ordered.extend(model_priorities)
        if primary_model not in ordered:
            ordered.insert(0, primary_model)

        # 追加用户已配置密钥的默认模型
        for provider, config in user_ctx.keys.items():
            llm_model, _ = decode_model_preferences(config.model_name)
            default_model = llm_model or model_provider_service.get_default_llm_model(provider)
            if default_model and default_model not in ordered:
                ordered.append(default_model)

        # 去重保持顺序
        seen: set[str] = set()
        unique: list[str] = []
        for model in ordered:
            if model and model not in seen:
                seen.add(model)
                unique.append(model)
        return unique

    def create_llm_with_fallback(
        self,
        user_ctx: UserKeyContext,
        model_name: str,
        temperature: float,
        top_p: Optional[float],
        max_tokens: Optional[int],
        model_priorities: Optional[list[str]] = None,
    ) -> tuple[ChatOpenAI, str, list[str]]:
        """
        按优先级创建首个可用 LLM 实例。

        Returns:
            (LLM 实例, 实际使用模型名, 完整优先级列表)
        """
        priority = self.build_model_priority(user_ctx, model_name, model_priorities)
        available_models = [
            model
            for model in priority
            if self.is_model_available(user_ctx.user_id, model)
        ]
        if not available_models:
            raise RuntimeError("所有大模型服务都不可用，请稍后再试")

        selected = available_models[0]
        provider = infer_llm_provider_from_model(selected)
        llm = create_chat_llm(
            user_ctx,
            model_name=selected,
            preferred_provider=provider,
            temperature=temperature,
            top_p=top_p,
            max_tokens=max_tokens,
        )
        return llm, selected, priority


llm_fallback_service = LlmFallbackService()
