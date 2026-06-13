"""
任务交付意图识别：报告 vs 演示文稿等。
"""

from __future__ import annotations

import re
from typing import Literal

DeliveryFormat = Literal["ppt", "report"]

# PPT / 演示文稿相关关键词（中英文）
PPT_KEYWORDS: tuple[str, ...] = (
    "ppt",
    "pptx",
    "幻灯片",
    "演示文稿",
    "演示材料",
    "汇报材料",
    "路演",
    "课件",
    "powerpoint",
    "presentation",
    "deck",
    "做一份ppt",
    "做个ppt",
    "制作ppt",
)


def detect_delivery_format(task: str) -> DeliveryFormat:
    """
    根据任务描述识别期望交付格式。

    Returns:
        ``ppt`` 或 ``report``。
    """
    if not task or not task.strip():
        return "report"
    normalized = task.lower().strip()
    for keyword in PPT_KEYWORDS:
        if keyword in normalized:
            return "ppt"
    # 「N 页 PPT」类正则
    if re.search(r"\d+\s*页.*(ppt|幻灯|演示)", normalized):
        return "ppt"
    if re.search(r"(ppt|幻灯|演示).*\d+\s*页", normalized):
        return "ppt"
    return "report"
