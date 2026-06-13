"""
LLM 错误建议增强服务（可选，默认关闭）。

在规则引擎基础上，启用后可追加 LLM 生成的结构化建议（需配置 OpenAI 兼容密钥）。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Optional

from app.core.config import settings
from app.utils.error_translator import ErrorSuggestion, translate_error_message

logger = logging.getLogger(__name__)


class ErrorAdvisorService:
    """错误建议增强：规则优先，可选 LLM 追加。"""

    async def advise(
        self,
        raw_error: str,
        *,
        context: Optional[dict[str, Any]] = None,
    ) -> list[ErrorSuggestion]:
        """生成修改建议列表。"""
        ctx = context or {}
        base = translate_error_message(raw_error, context=ctx)
        suggestions = list(base.suggestions)

        if not settings.error_advisor_enabled:
            return suggestions

        try:
            llm_suggestions = await self._llm_advise(raw_error, ctx)
            seen = {s.title for s in suggestions}
            for item in llm_suggestions:
                if item.title not in seen:
                    suggestions.append(item)
                    seen.add(item.title)
        except Exception as exc:
            logger.warning("LLM 错误建议生成失败: %s", exc)

        return sorted(suggestions, key=lambda s: s.priority)

    async def _llm_advise(
        self,
        raw_error: str,
        context: dict[str, Any],
    ) -> list[ErrorSuggestion]:
        """调用 OpenAI 兼容接口生成 JSON 建议（轻量，无 Agent 依赖）。"""
        api_key = settings.openai_api_key_for_moderation
        if not api_key:
            logger.info("error_advisor 已启用但未配置 openai_api_key_for_moderation，跳过 LLM")
            return []

        from openai import AsyncOpenAI

        client = AsyncOpenAI(api_key=api_key)
        prompt = (
            "你是企业 AI 工作台运维助手。根据执行错误输出 1-2 条中文修改建议。\n"
            "仅返回 JSON 数组，每项含 title、description、priority。\n"
            f"错误: {raw_error[:400]}\n"
            f"上下文: {json.dumps(context, ensure_ascii=False)[:400]}"
        )
        response = await client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "只输出合法 JSON 数组，不要 markdown。"},
                {"role": "user", "content": prompt},
            ],
            temperature=0.2,
            max_tokens=400,
        )
        answer = (response.choices[0].message.content or "").strip()
        match = re.search(r"\[[\s\S]*\]", answer)
        if not match:
            return []

        items = json.loads(match.group())
        suggestions: list[ErrorSuggestion] = []
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            desc = str(item.get("description") or "").strip()
            if title and desc:
                suggestions.append(
                    ErrorSuggestion(
                        title=title,
                        description=desc,
                        priority=int(item.get("priority") or idx + 10),
                    )
                )
        return suggestions


error_advisor_service = ErrorAdvisorService()
