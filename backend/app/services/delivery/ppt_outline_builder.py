"""
从群聊交付物 Markdown 构建 PPT 幻灯片大纲。
"""

from __future__ import annotations

import json
import re
from typing import Any


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
