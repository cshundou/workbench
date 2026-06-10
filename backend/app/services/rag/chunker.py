"""
智能分块层：混合分块 + 语义分块 + 重叠分片 + 标题锚定。
"""

import re
from typing import Any

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.embeddings import OpenAIEmbeddings
from langchain_experimental.text_splitter import SemanticChunker

from app.core.logging import get_logger

logger = get_logger(__name__)


class IntelligentChunker:
    """智能文档分块器。"""

    def __init__(self, embedding_model: str = "text-embedding-ada-002") -> None:
        self.embeddings = OpenAIEmbeddings(model=embedding_model)
        self.semantic_chunker = SemanticChunker(
            self.embeddings,
            breakpoint_threshold_type="percentile",
            breakpoint_threshold_amount=95,
        )
        self.recursive_splitter = RecursiveCharacterTextSplitter(
            chunk_size=512,
            chunk_overlap=100,
            separators=["\n\n", "\n", ". ", " ", ""],
        )

    def split_document(self, content: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
        """
        智能分块，返回带元数据的块列表。

        Args:
            content: 文档纯文本。
            metadata: 基础元数据（document_id、kb_id 等）。

        Returns:
            分块列表，每项含 content 与 metadata。
        """
        headings = self._extract_headings(content)
        semantic_chunks = self.semantic_chunker.split_text(content)
        final_chunks: list[dict[str, Any]] = []

        for index, chunk in enumerate(semantic_chunks):
            if len(chunk) > 1024:
                sub_chunks = self.recursive_splitter.split_text(chunk)
                for sub_index, sub_chunk in enumerate(sub_chunks):
                    final_chunks.append(
                        {
                            "content": sub_chunk,
                            "metadata": {
                                **metadata,
                                "chunk_index": f"{index}.{sub_index}",
                                "parent_chunk_id": index,
                                "heading": self._get_current_heading(chunk, headings),
                            },
                        }
                    )
            else:
                final_chunks.append(
                    {
                        "content": chunk,
                        "metadata": {
                            **metadata,
                            "chunk_index": str(index),
                            "heading": self._get_current_heading(chunk, headings),
                        },
                    }
                )

        logger.info("文档分块完成 chunks=%s", len(final_chunks))
        return final_chunks

    def _extract_headings(self, content: str) -> list[tuple[int, int, str]]:
        """提取文档中的标题结构。"""
        heading_pattern = r"^(#{1,6})\s+(.+)$|^(.+)\n[=-]+$"
        headings: list[tuple[int, int, str]] = []
        lines = content.split("\n")

        for line_index, line in enumerate(lines):
            match = re.match(heading_pattern, line, re.MULTILINE)
            if match:
                level = len(match.group(1)) if match.group(1) else 1
                text = match.group(2) if match.group(2) else match.group(3)
                headings.append((line_index, level, text.strip()))

        return headings

    def _get_current_heading(
        self,
        chunk: str,
        headings: list[tuple[int, int, str]],
    ) -> str:
        """获取当前块所属的标题。"""
        if not headings:
            return ""

        for _line_num, _level, text in reversed(headings):
            if text in chunk:
                return text

        return headings[-1][2] if headings else ""
