"""
PPT 文件生成服务（兼容层，委托 app.services.ppt.ppt_generator）。
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.services.ppt.ppt_generator import PptGenerator, ppt_generator

logger = logging.getLogger(__name__)


class PptGeneratorService:
    """演示文稿生成器（向后兼容包装）。"""

    def __init__(self, base_dir: str | None = None) -> None:
        self._engine = PptGenerator(base_dir=base_dir)

    def resolve_session_dir(self, tenant_id: int, session_id: int) -> Path:
        """获取会话交付物目录并确保存在。"""
        return self._engine.resolve_output_dir(tenant_id, session_id)

    def generate_pptx(
        self,
        tenant_id: int,
        session_id: int,
        outline: dict[str, Any],
        *,
        filename: str | None = None,
    ) -> dict[str, Any]:
        """
        根据大纲生成 PPTX 文件。

        Returns:
            {"filename", "file_path", "size", "slide_count", "template_id"}
        """
        result = self._engine.generate_for_session(
            tenant_id,
            session_id,
            outline,
            filename=filename,
        )
        logger.info(
            "PPT 已生成 tenant=%s session=%s path=%s slides=%d",
            tenant_id,
            session_id,
            result["file_path"],
            result["slide_count"],
        )
        return result

    def get_file_path(
        self,
        tenant_id: int,
        session_id: int,
        filename: str,
    ) -> Path | None:
        """校验并返回交付物文件路径（防目录穿越）。"""
        return self._engine.get_file_path(tenant_id, session_id, filename)


ppt_generator_service = PptGeneratorService()
