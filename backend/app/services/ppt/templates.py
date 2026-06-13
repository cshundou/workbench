"""
PPT 内置模板：配色、字体、母版样式。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

TemplateId = Literal["business_minimal", "tech_modern"]


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
    body_size_pt: int


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
        title_size_pt=32,
        body_size_pt=18,
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
        title_size_pt=34,
        body_size_pt=17,
    ),
}


def get_template(template_id: str) -> PptTemplate:
    """获取模板，未知 ID 回退商务简约。"""
    return TEMPLATES.get(template_id, TEMPLATES["business_minimal"])
