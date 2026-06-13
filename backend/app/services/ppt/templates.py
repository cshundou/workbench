"""
PPT 内置模板：5 套场景化配色、字体、版式库。
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

TemplateId = Literal[
    "business_minimal",
    "business_report",
    "tech_modern",
    "tech_proposal",
    "data_analysis",
    "year_summary",
    "minimal_share",
]


@dataclass(frozen=True)
class PptTemplate:
    """模板定义。"""

    template_id: str
    name: str
    primary_color: str
    secondary_color: str
    accent_color: str
    background_color: str
    title_font: str
    body_font: str
    title_size_pt: int
    subtitle_size_pt: int
    body_size_pt: int
    caption_size_pt: int
    supported_layouts: tuple[str, ...] = field(
        default_factory=lambda: (
            "cover",
            "toc",
            "split_horizontal",
            "split_vertical",
            "card_row",
            "chart_focus",
            "process_steps",
            "matrix",
        )
    )


TEMPLATES: dict[str, PptTemplate] = {
    "business_minimal": PptTemplate(
        template_id="business_minimal",
        name="商务简约",
        primary_color="1F4E79",
        secondary_color="2E75B6",
        accent_color="FFC000",
        background_color="FFFFFF",
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
        title_size_pt=36,
        subtitle_size_pt=20,
        body_size_pt=18,
        caption_size_pt=14,
    ),
    "business_report": PptTemplate(
        template_id="business_report",
        name="商务汇报",
        primary_color="1A365D",
        secondary_color="4A5568",
        accent_color="3182CE",
        background_color="F7FAFC",
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
        title_size_pt=34,
        subtitle_size_pt=20,
        body_size_pt=18,
        caption_size_pt=14,
    ),
    "tech_modern": PptTemplate(
        template_id="tech_modern",
        name="科技风",
        primary_color="0B1F3A",
        secondary_color="00B4D8",
        accent_color="90E0EF",
        background_color="F8FAFC",
        title_font="Arial",
        body_font="Arial",
        title_size_pt=36,
        subtitle_size_pt=20,
        body_size_pt=17,
        caption_size_pt=14,
    ),
    "tech_proposal": PptTemplate(
        template_id="tech_proposal",
        name="科技方案",
        primary_color="0F172A",
        secondary_color="3B82F6",
        accent_color="06B6D4",
        background_color="FFFFFF",
        title_font="Arial",
        body_font="Arial",
        title_size_pt=36,
        subtitle_size_pt=20,
        body_size_pt=17,
        caption_size_pt=14,
    ),
    "data_analysis": PptTemplate(
        template_id="data_analysis",
        name="数据分析",
        primary_color="2D3748",
        secondary_color="38A169",
        accent_color="68D391",
        background_color="FFFFFF",
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
        title_size_pt=32,
        subtitle_size_pt=18,
        body_size_pt=16,
        caption_size_pt=13,
    ),
    "year_summary": PptTemplate(
        template_id="year_summary",
        name="年终总结",
        primary_color="991B1B",
        secondary_color="B45309",
        accent_color="F59E0B",
        background_color="FFFBEB",
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
        title_size_pt=38,
        subtitle_size_pt=22,
        body_size_pt=18,
        caption_size_pt=14,
    ),
    "minimal_share": PptTemplate(
        template_id="minimal_share",
        name="简约分享",
        primary_color="111827",
        secondary_color="6B7280",
        accent_color="374151",
        background_color="FFFFFF",
        title_font="Microsoft YaHei",
        body_font="Microsoft YaHei",
        title_size_pt=32,
        subtitle_size_pt=18,
        body_size_pt=16,
        caption_size_pt=14,
    ),
}

# 旧 ID 别名
TEMPLATE_ALIASES: dict[str, str] = {
    "business_minimal": "business_report",
    "tech_modern": "tech_proposal",
}


def get_template(template_id: str) -> PptTemplate:
    """获取模板，未知 ID 回退商务汇报。"""
    resolved = TEMPLATE_ALIASES.get(template_id, template_id)
    return TEMPLATES.get(resolved, TEMPLATES["business_report"])


def match_layout_for_slide(slide: dict) -> str:
    """根据页面内容自动匹配最优版式。"""
    slide_type = str(slide.get("slide_type") or slide.get("type") or "content").lower()
    layout = str(slide.get("layout") or "").lower()
    if layout:
        return layout
    if slide_type in ("cover", "ending"):
        return "cover" if slide_type == "cover" else "cover"
    if slide_type in ("toc", "section"):
        return "toc"
    if slide.get("chart") or slide.get("table"):
        return "chart_focus"
    bullets = slide.get("bullets") or slide.get("points") or []
    title = str(slide.get("title") or "")
    if any(kw in title for kw in ("流程", "步骤", "阶段")):
        return "process_steps"
    if any(kw in title for kw in ("矩阵", "象限", "四象限")):
        return "matrix"
    if isinstance(bullets, list) and len(bullets) >= 3:
        return "card_row"
    if len(bullets) <= 3 and (slide.get("chart") or slide.get("image_hint")):
        return "split_horizontal"
    return "split_vertical"
