"""
文档加载器扩展单元测试。
"""

import tempfile
from pathlib import Path

import pytest

from app.services.rag.document_loader import DocumentLoader


class TestDocumentLoader:
    """DocumentLoader 各格式与边界。"""

    @pytest.fixture
    def loader(self) -> DocumentLoader:
        return DocumentLoader()

    def test_unsupported_format_raises(self, loader: DocumentLoader) -> None:
        with pytest.raises(ValueError, match="不支持的文件格式"):
            loader.load_document("/tmp/x.unknown", ".unknown")

    def test_get_supported_extensions(self, loader: DocumentLoader) -> None:
        extensions = loader.get_supported_extensions()
        assert ".pdf" in extensions
        assert ".pptx" in extensions

    def test_validate_file_not_exists(self, loader: DocumentLoader) -> None:
        with pytest.raises(FileNotFoundError):
            loader.validate_file_exists("/nonexistent/file.txt")

    def test_load_text_file(self, loader: DocumentLoader) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("Hello RAG\n\nWorld")
            path = tmp.name
        try:
            content = loader.load_document(path, ".txt")
            assert "Hello RAG" in content
            assert "World" in content
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_markdown_file(self, loader: DocumentLoader) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
            tmp.write("# Title\n\nContent")
            path = tmp.name
        try:
            content = loader.load_document(path, ".md")
            assert "Title" in content
        finally:
            Path(path).unlink(missing_ok=True)

    def test_load_html_file(self, loader: DocumentLoader) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".html", delete=False) as tmp:
            tmp.write("<html><body><p>Hello</p><script>bad</script></body></html>")
            path = tmp.name
        try:
            content = loader.load_document(path, ".html")
            assert "Hello" in content
            assert "bad" not in content
        finally:
            Path(path).unlink(missing_ok=True)

    def test_extension_without_dot(self, loader: DocumentLoader) -> None:
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as tmp:
            tmp.write("plain")
            path = tmp.name
        try:
            content = loader.load_document(path, "txt")
            assert "plain" in content
        finally:
            Path(path).unlink(missing_ok=True)
