"""
文档接入层：支持 PDF、MD、TXT、Excel、Word、HTML 等格式加载与清洗。
"""

from pathlib import Path
from typing import Callable

from bs4 import BeautifulSoup
from docx import Document as DocxDocument
from unstructured.cleaners.core import clean_extra_whitespace
from unstructured.partition.auto import partition
from unstructured.partition.pptx import partition_pptx

from app.core.logging import get_logger

logger = get_logger(__name__)


class DocumentLoader:
    """文档加载器，按扩展名路由到对应解析方法。"""

    def __init__(self) -> None:
        self.supported_formats: dict[str, Callable[[str], str]] = {
            ".pdf": self.load_pdf,
            ".txt": self.load_text,
            ".md": self.load_markdown,
            ".docx": self.load_docx,
            ".xlsx": self.load_excel,
            ".html": self.load_html,
            ".ppt": self.load_pptx,
            ".pptx": self.load_pptx,
        }

    def load_document(self, file_path: str, file_type: str) -> str:
        """
        加载并清洗文档。

        Args:
            file_path: 文件绝对路径。
            file_type: 文件扩展名（含点），如 .pdf。

        Returns:
            清洗后的纯文本内容。

        Raises:
            ValueError: 不支持的文件格式。
        """
        normalized_type = file_type.lower()
        if not normalized_type.startswith("."):
            normalized_type = f".{normalized_type}"

        if normalized_type not in self.supported_formats:
            raise ValueError(f"不支持的文件格式: {file_type}")

        logger.info("开始加载文档 path=%s type=%s", file_path, normalized_type)
        content = self.supported_formats[normalized_type](file_path)
        content = clean_extra_whitespace(content)
        content = content.replace("\x00", "")
        return content

    def load_pdf(self, file_path: str) -> str:
        """加载 PDF 文档，处理水印和乱码。"""
        elements = partition(filename=file_path, strategy="fast")
        return "\n\n".join(
            [str(element) for element in elements if len(str(element).strip()) > 0]
        )

    def load_text(self, file_path: str) -> str:
        """加载纯文本文档。"""
        with open(file_path, "r", encoding="utf-8") as file:
            return file.read()

    def load_markdown(self, file_path: str) -> str:
        """加载 Markdown 文档。"""
        return self.load_text(file_path)

    def load_docx(self, file_path: str) -> str:
        """加载 Word 文档。"""
        doc = DocxDocument(file_path)
        return "\n\n".join([paragraph.text for paragraph in doc.paragraphs])

    def load_excel(self, file_path: str) -> str:
        """加载 Excel 文档。"""
        import pandas as pd

        dataframe = pd.read_excel(file_path)
        return dataframe.to_string(index=False)

    def load_html(self, file_path: str) -> str:
        """加载 HTML 文档。"""
        with open(file_path, "r", encoding="utf-8") as file:
            soup = BeautifulSoup(file.read(), "html.parser")
        return soup.get_text()

    def load_pptx(self, file_path: str) -> str:
        """加载 PPT/PPTX 文档。"""
        elements = partition_pptx(filename=file_path)
        return "\n\n".join(
            [str(element) for element in elements if len(str(element).strip()) > 0]
        )

    def get_supported_extensions(self) -> list[str]:
        """返回支持的文件扩展名列表。"""
        return list(self.supported_formats.keys())

    def validate_file_exists(self, file_path: str) -> None:
        """校验文件是否存在。"""
        if not Path(file_path).is_file():
            raise FileNotFoundError(f"文件不存在: {file_path}")
