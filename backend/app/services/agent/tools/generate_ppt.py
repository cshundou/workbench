"""
PPT 生成工具：供 Agent 调用，输出 .pptx 文件路径。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.user import User
from app.services.agent.tools.base import BaseTool, ToolResult
from app.services.ppt.ppt_generator import ppt_generator
from app.services.ppt.schemas import PptOutline
from app.services.user_key_context import UserKeyContext

logger = get_logger(__name__)


class GeneratePptTool(BaseTool):
    """根据结构化大纲生成 PPTX 演示文稿。"""

    name = "generate_ppt"
    description = (
        "根据结构化大纲生成 PPTX 演示文稿文件，支持封面、目录、正文、过渡页、结尾页，"
        "以及图表、表格等元素。返回文件路径与页数。"
    )
    parameters = {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "integer",
                "description": "群聊会话 ID，用于写入交付物目录",
            },
            "outline": {
                "type": "object",
                "description": (
                    "PPT 大纲，含 title、subtitle、template_id(business_minimal|tech_modern)、"
                    "slides 数组（slide_type/title/bullets/chart/table）"
                ),
            },
            "filename": {
                "type": "string",
                "description": "输出文件名，可选",
            },
            "template_id": {
                "type": "string",
                "description": "模板 ID：business_minimal 或 tech_modern",
            },
        },
        "required": ["session_id", "outline"],
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

    async def execute(self, parameters: dict[str, Any]) -> ToolResult:
        """执行 PPT 生成。"""
        session_id = parameters.get("session_id")
        outline_raw = parameters.get("outline")
        if not session_id or not outline_raw:
            return ToolResult(
                success=False,
                content=None,
                error="session_id 与 outline 为必填参数",
            )
        try:
            session_id_int = int(session_id)
        except (TypeError, ValueError):
            return ToolResult(success=False, content=None, error="session_id 必须为整数")

        if not isinstance(outline_raw, dict):
            return ToolResult(success=False, content=None, error="outline 必须为 JSON 对象")

        outline_data = dict(outline_raw)
        template_id = parameters.get("template_id")
        if template_id and not outline_data.get("template_id"):
            outline_data["template_id"] = template_id

        try:
            outline = PptOutline.from_dict(outline_data)
            result = ppt_generator.generate_for_session(
                self.tenant_id,
                session_id_int,
                outline,
                filename=parameters.get("filename"),
            )
            download_path = (
                f"/api/v1/group-chat/sessions/{session_id_int}"
                f"/deliverables/{result['filename']}"
            )
            payload = {
                **result,
                "download_path": download_path,
            }
            logger.info(
                "GeneratePptTool 成功 tenant=%s session=%s slides=%d",
                self.tenant_id,
                session_id_int,
                result["slide_count"],
            )
            return ToolResult(success=True, content=payload)
        except Exception as exc:
            logger.exception("GeneratePptTool 执行失败: %s", exc)
            return ToolResult(success=False, content=None, error=str(exc))
