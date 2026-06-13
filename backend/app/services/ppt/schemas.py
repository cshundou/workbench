"""
PPT 结构化大纲 Schema（与 Agent / 群聊交付物兼容）。
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

SlideType = Literal["cover", "toc", "content", "section", "ending"]
ChartType = Literal["bar", "line", "pie"]
TemplateId = Literal["business_minimal", "tech_modern"]


class ChartSpec(BaseModel):
    """幻灯片内嵌图表。"""

    chart_type: ChartType = "bar"
    title: str = ""
    categories: list[str] = Field(default_factory=list)
    series: list[dict[str, Any]] = Field(
        default_factory=list,
        description='[{"name": "系列名", "values": [1,2,3]}]',
    )


class TableSpec(BaseModel):
    """幻灯片表格。"""

    headers: list[str] = Field(default_factory=list)
    rows: list[list[str]] = Field(default_factory=list)


class SlideSpec(BaseModel):
    """单页幻灯片。"""

    slide_type: SlideType = "content"
    title: str = ""
    subtitle: str = ""
    bullets: list[str] = Field(default_factory=list)
    paragraphs: list[str] = Field(default_factory=list)
    chart: Optional[ChartSpec] = None
    table: Optional[TableSpec] = None


class PptOutline(BaseModel):
    """完整演示文稿大纲。"""

    title: str = "演示文稿"
    subtitle: str = ""
    template_id: TemplateId = "business_minimal"
    slides: list[SlideSpec] = Field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PptOutline":
        """从 dict / JSON 构建大纲（兼容旧 slides 格式）。"""
        slides_raw = data.get("slides") or []
        slides: list[SlideSpec] = []
        for item in slides_raw:
            if not isinstance(item, dict):
                continue
            slide_type = item.get("slide_type") or item.get("type") or "content"
            chart_data = item.get("chart")
            chart = ChartSpec(**chart_data) if isinstance(chart_data, dict) else None
            table_data = item.get("table")
            table = TableSpec(**table_data) if isinstance(table_data, dict) else None
            bullets = item.get("bullets") or item.get("points") or []
            if not isinstance(bullets, list):
                bullets = [str(bullets)]
            slides.append(
                SlideSpec(
                    slide_type=slide_type,
                    title=str(item.get("title") or item.get("heading") or ""),
                    subtitle=str(item.get("subtitle") or ""),
                    bullets=[str(b) for b in bullets],
                    paragraphs=[
                        str(p) for p in (item.get("paragraphs") or []) if str(p).strip()
                    ],
                    chart=chart,
                    table=table,
                )
            )
        template = data.get("template_id") or data.get("template") or "business_minimal"
        if template not in ("business_minimal", "tech_modern"):
            template = "business_minimal"
        return cls(
            title=str(data.get("title") or "演示文稿"),
            subtitle=str(data.get("subtitle") or ""),
            template_id=template,
            slides=slides,
        )
