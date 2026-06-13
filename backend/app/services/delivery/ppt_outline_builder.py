"""
从群聊交付物 Markdown 构建 PPT 幻灯片大纲。
"""

from __future__ import annotations

import json
import re
from typing import Any

# 八大必备模块默认页（SCQA + One Slide One Idea）
STANDARD_MODULE_SLIDES: list[dict[str, Any]] = [
    {"slide_type": "cover", "title": "{title}", "subtitle": "{subtitle}"},
    {"slide_type": "toc", "title": "目录", "bullets": []},
    {"slide_type": "content", "title": "背景与现状", "bullets": ["行业/业务情境", "当前面临的核心挑战"]},
    {"slide_type": "content", "title": "核心问题与目标", "bullets": ["待解决的关键问题", "本次汇报目标"]},
    {"slide_type": "content", "title": "分析与方案", "bullets": ["核心观点", "支撑论据"]},
    {"slide_type": "content", "title": "关键数据", "bullets": ["指标说明（来源：待补充）"], "chart": None},
    {"slide_type": "content", "title": "总结与建议", "bullets": ["核心结论", "下一步行动建议"]},
    {"slide_type": "ending", "title": "谢谢聆听"},
]

MIN_PAGES_BY_COMPLEXITY: dict[str, int] = {"simple": 8, "medium": 12, "complex": 18}


def enforce_standard_structure(
    outline: dict[str, Any],
    *,
    title: str = "演示文稿",
    subtitle: str = "",
    complexity: str = "medium",
) -> dict[str, Any]:
    """补全八大模块结构，确保页数达标。"""
    slides = list(outline.get("slides") or [])
    if not slides:
        slides = [
            {**s, "title": s["title"].format(title=title, subtitle=subtitle or "多 Agent 协同生成")}
            if "{title}" in s.get("title", "") else s
            for s in STANDARD_MODULE_SLIDES
        ]
    else:
        modules_found = set()
        for slide in slides:
            if not isinstance(slide, dict):
                continue
            st = str(slide.get("slide_type", "")).lower()
            t = str(slide.get("title", "")).lower()
            if st == "cover" or "封面" in t:
                modules_found.add("cover")
            if st == "toc" or "目录" in t:
                modules_found.add("toc")
            if "背景" in t or "现状" in t:
                modules_found.add("background")
            if "问题" in t or "目标" in t:
                modules_found.add("problem")
            if "方案" in t or "分析" in t:
                modules_found.add("solution")
            if "数据" in t or slide.get("chart") or slide.get("table"):
                modules_found.add("data")
            if "总结" in t or "建议" in t or "结论" in t:
                modules_found.add("summary")
            if st == "ending" or "谢谢" in t:
                modules_found.add("ending")

        insertions: list[dict[str, Any]] = []
        if "background" not in modules_found:
            insertions.append(
                {"slide_type": "content", "title": "背景与现状", "bullets": ["情境说明", "核心冲突"]}
            )
        if "problem" not in modules_found:
            insertions.append(
                {"slide_type": "content", "title": "核心问题与目标", "bullets": ["问题定义", "汇报目标"]}
            )
        if "solution" not in modules_found:
            insertions.append(
                {"slide_type": "content", "title": "分析与方案", "bullets": ["核心观点", "实施路径"]}
            )
        if "data" not in modules_found:
            insertions.append(
                {
                    "slide_type": "content",
                    "title": "关键数据",
                    "bullets": ["数据来源：待标注"],
                }
            )
        if "summary" not in modules_found:
            insertions.append(
                {"slide_type": "content", "title": "总结与建议", "bullets": ["核心结论", "行动建议"]}
            )
        # 在 ending 前插入缺失模块
        ending_idx = next(
            (i for i, s in enumerate(slides) if str(s.get("slide_type", "")).lower() == "ending"),
            len(slides),
        )
        for offset, item in enumerate(insertions):
            slides.insert(ending_idx + offset, item)

    min_pages = MIN_PAGES_BY_COMPLEXITY.get(complexity, 12)
    while len(slides) < min_pages:
        idx = len(slides) - 1
        slides.insert(
            idx,
            {
                "slide_type": "content",
                "title": f"补充要点 {len(slides)}",
                "bullets": ["核心观点（One Slide One Idea）", "论据与数据（来源：待标注）"],
            },
        )

    outline["slides"] = slides[: max(min_pages + 3, 25)]
    outline.setdefault("title", title)
    outline.setdefault("subtitle", subtitle)
    return outline


def _extract_bullets(block: str) -> list[str]:
    """从文本块提取要点列表。"""
    bullets: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        match = re.match(r"^[-*•·]\s+(.+)$", stripped)
        if match:
            bullets.append(match.group(1).strip())
        elif re.match(r"^\d+[.)]\s+(.+)$", stripped):
            bullets.append(re.sub(r"^\d+[.)]\s+", "", stripped).strip())
    return bullets


def _split_sections(text: str) -> list[tuple[str, str]]:
    """按 Markdown 标题切分章节。"""
    sections: list[tuple[str, str]] = []
    current_title = ""
    current_lines: list[str] = []

    for line in text.splitlines():
        heading = re.match(r"^(#{1,3})\s+(.+)$", line.strip())
        if heading:
            if current_title or current_lines:
                sections.append((current_title, "\n".join(current_lines).strip()))
            current_title = heading.group(2).strip()
            current_lines = []
        else:
            current_lines.append(line)

    if current_title or current_lines:
        sections.append((current_title, "\n".join(current_lines).strip()))
    return sections


def _normalize_slide_item(item: dict[str, Any]) -> dict[str, Any]:
    """标准化单页幻灯片字段。"""
    slide_type = item.get("slide_type") or item.get("type") or "content"
    title = str(item.get("title") or item.get("heading") or "").strip()
    subtitle = str(item.get("subtitle") or "").strip()
    bullets_raw = item.get("bullets") or item.get("points") or []
    bullets = (
        [str(b).strip() for b in bullets_raw if str(b).strip()]
        if isinstance(bullets_raw, list)
        else []
    )
    body = str(item.get("content") or item.get("body") or "").strip()
    if not bullets and body:
        bullets = _extract_bullets(body) or [body[:200]]

    slide: dict[str, Any] = {
        "slide_type": slide_type,
        "title": title or "内容",
        "bullets": bullets[:8],
    }
    if subtitle:
        slide["subtitle"] = subtitle
    if item.get("chart"):
        slide["chart"] = item["chart"]
    if item.get("table"):
        slide["table"] = item["table"]
    return slide


def _parse_json_outline(text: str) -> dict[str, Any] | None:
    """尝试解析 Agent 输出的 JSON 大纲（含 slides / template_id）。"""
    text = text.strip()
    if not text:
        return None
    candidates = [text]
    fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if fence:
        candidates.insert(0, fence.group(1).strip())
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if not isinstance(data, dict):
            if isinstance(data, list):
                data = {"slides": data}
            else:
                continue
        slides_raw = data.get("slides")
        if not isinstance(slides_raw, list):
            continue
        slides = [
            _normalize_slide_item(item)
            for item in slides_raw
            if isinstance(item, dict)
        ]
        if not slides:
            continue
        template_id = data.get("template_id") or data.get("template") or "business_minimal"
        return {
            "title": str(data.get("title") or "演示文稿"),
            "subtitle": str(data.get("subtitle") or ""),
            "template_id": template_id,
            "slides": slides,
        }
    return None


def _build_default_structure(
    title: str,
    content_slides: list[dict[str, Any]],
    *,
    subtitle: str = "",
    template_id: str = "business_minimal",
) -> dict[str, Any]:
    """构建含封面、目录、正文、结尾的标准结构。"""
    toc_titles = [s.get("title", "") for s in content_slides if s.get("title")]
    slides: list[dict[str, Any]] = [
        {
            "slide_type": "cover",
            "title": title,
            "subtitle": subtitle or "多 Agent 协同生成",
        },
    ]
    if toc_titles:
        slides.append({"slide_type": "toc", "title": "目录", "bullets": toc_titles[:12]})
    slides.extend(content_slides)
    slides.append({"slide_type": "ending", "title": "谢谢聆听"})
    return {
        "title": title,
        "subtitle": subtitle,
        "template_id": template_id,
        "slides": slides,
    }


def build_ppt_outline(
    task: str,
    deliverables: list[dict[str, Any]],
    *,
    max_slides: int = 15,
) -> dict[str, Any]:
    """
    汇总 deliverables 为 PPT 大纲。

    Returns:
        {"title", "subtitle", "template_id", "slides": [...]}
    """
    combined_parts: list[str] = []
    parsed_outline: dict[str, Any] | None = None

    for item in deliverables:
        content = str(item.get("content") or "").strip()
        if content:
            combined_parts.append(content)
            if parsed_outline is None:
                parsed_outline = _parse_json_outline(content)

    combined = "\n\n".join(combined_parts).strip()
    title = task.strip()[:80] or "演示文稿"

    if parsed_outline:
        parsed_outline["title"] = parsed_outline.get("title") or title
        slides = parsed_outline.get("slides") or []
        if slides and slides[0].get("slide_type") not in ("cover", "toc", "ending"):
            return _build_default_structure(
                parsed_outline["title"],
                slides[: max_slides - 3],
                subtitle=parsed_outline.get("subtitle", ""),
                template_id=str(parsed_outline.get("template_id") or "business_minimal"),
            )
        parsed_outline["slides"] = slides[:max_slides]
        return parsed_outline

    content_slides: list[dict[str, Any]] = []
    sections = _split_sections(combined)

    if sections:
        for sec_title, body in sections:
            clean_title = sec_title or "内容"
            skip_titles = ("任务交付报告", "任务", "审核结论")
            if any(skip in clean_title for skip in skip_titles) and not body:
                continue
            bullets = _extract_bullets(body)
            if not bullets and body:
                paragraphs = [p.strip() for p in body.split("\n\n") if p.strip()]
                bullets = [p[:120] for p in paragraphs[:5]]
            if not bullets:
                bullets = [body[:150]] if body else [clean_title]
            content_slides.append(
                {"slide_type": "content", "title": clean_title[:60], "bullets": bullets[:6]}
            )
    elif combined:
        paragraphs = [p.strip() for p in combined.split("\n\n") if p.strip()]
        for idx, para in enumerate(paragraphs[: max_slides - 3]):
            bullets = _extract_bullets(para) or [para[:150]]
            content_slides.append(
                {
                    "slide_type": "content",
                    "title": f"要点 {idx + 1}",
                    "bullets": bullets[:6],
                }
            )
    else:
        content_slides.append(
            {
                "slide_type": "content",
                "title": title,
                "bullets": ["汇报主题", task[:120]],
            }
        )

    return _build_default_structure(title, content_slides[: max_slides - 3])


def build_ppt_outline_with_quality(
    task: str,
    deliverables: list[dict[str, Any]],
    *,
    max_slides: int = 20,
    complexity: str = "medium",
) -> dict[str, Any]:
    """汇总交付物并强制八大模块结构。"""
    outline = build_ppt_outline(task, deliverables, max_slides=max_slides)
    return enforce_standard_structure(
        outline,
        title=outline.get("title") or task[:80],
        subtitle=outline.get("subtitle") or "",
        complexity=complexity,
    )
