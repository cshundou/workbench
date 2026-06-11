"""
引用溯源层：基于上下文生成带引用标注的回答，支持流式输出。
"""

from collections.abc import AsyncGenerator
from typing import Any, Optional

from langchain.prompts import PromptTemplate
from langchain_openai import ChatOpenAI

from app.core.logging import get_logger
from app.services.user_key_context import UserKeyContext, create_chat_llm

logger = get_logger(__name__)

ANSWER_PROMPT = """
基于以下上下文回答用户的问题。如果上下文没有相关信息，请明确说明不知道。
回答时请在引用的内容后面标注对应的来源编号，例如：[1]

上下文：
{context}

问题：{question}

回答：
"""


class AnswerGenerator:
    """带引用溯源的问答生成器。"""

    def __init__(
        self,
        user_ctx: UserKeyContext,
        model_name: Optional[str] = None,
        llm: Optional[ChatOpenAI] = None,
    ) -> None:
        self.user_ctx = user_ctx
        self.llm = llm or create_chat_llm(user_ctx, model_name=model_name, temperature=0)
        self._model_name = model_name or getattr(self.llm, "model_name", "unknown")
        self.prompt_template = PromptTemplate(
            input_variables=["context", "question"],
            template=ANSWER_PROMPT,
        )

    @property
    def model_name(self) -> str:
        """当前使用的模型名称。"""
        return str(getattr(self.llm, "model_name", self._model_name))

    def generate_answer(
        self,
        query: str,
        context: str,
        sources: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """
        生成带引用的回答。

        Args:
            query: 用户问题。
            context: 拼接后的上下文。
            sources: 引用来源列表。

        Returns:
            含 answer 与 sources 的字典。
        """
        chain = self.prompt_template | self.llm
        answer = chain.invoke({"context": context, "question": query})
        logger.info("问答生成完成 query=%s sources=%s", query[:50], len(sources))
        return {
            "answer": answer.content,
            "sources": sources,
            "llm_response": answer,
            "model_name": self.model_name,
        }

    async def generate_answer_stream(
        self,
        query: str,
        context: str,
        sources: list[dict[str, Any]],
    ) -> AsyncGenerator[dict[str, Any], None]:
        """
        流式生成带引用的回答（用于 SSE）。

        Args:
            query: 用户问题。
            context: 拼接后的上下文。
            sources: 引用来源列表。

        Yields:
            SSE 事件字典，type 为 token / citation / done。
        """
        chain = self.prompt_template | self.llm
        last_chunk: Any = None
        try:
            async for chunk in chain.astream({"context": context, "question": query}):
                last_chunk = chunk
                content = chunk.content if hasattr(chunk, "content") else str(chunk)
                if content:
                    yield {"type": "token", "content": content}
            yield {"type": "citation", "sources": sources}
            if last_chunk is not None:
                yield {
                    "type": "usage",
                    "llm_response": last_chunk,
                    "model_name": self.model_name,
                }
            yield {"type": "done"}
            logger.info("流式问答完成 query=%s", query[:50])
        except Exception as exc:
            logger.error("流式问答失败: %s", exc)
            yield {"type": "error", "message": str(exc)}
