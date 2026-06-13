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


def _parse_json_slides(text: str) -> list[dict[str, Any]] | None:
    """尝试解析 Agent 输出的 JSON 幻灯片数组。"""
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
        if isinstance(data, dict) and isinstance(data.get("slides"), list):
            data = data["slides"]
        if not isinstance(data, list):
            continue
        slides: list[dict[str, Any]] = []
        for item in data:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or item.get("heading") or "").strip()
            bullets_raw = item.get("bullets") or item.get("points") or []
            bullets = (
                [str(b).strip() for b in bullets_raw if str(b).strip()]
                if isinstance(bullets_raw, list)
                else []
            )
            body = str(item.get("content") or item.get("body") or "").strip()
            if not bullets and body:
                bullets = _extract_bullets(body) or [body[:200]]
            if title or bullets:
                slides.append({"title": title or "内容", "bullets": bullets[:8]})
        if slides:
            return slides
    return None


def build_ppt_outline(
    task: str,
    deliverables: list[dict[str, Any]],
    *,
    max_slides: int = 15,
) -> dict[str, Any]:
    """
    汇总 deliverables 为 PPT 大纲。

    Returns:
        {"title": str, "slides": [{"title": str, "bullets": list[str]}]}
    """
    combined_parts: list[str] = []
    for item in deliverables:
        content = str(item.get("content") or "").strip()
        if content:
            combined_parts.append(content)

    combined = "\n\n".join(combined_parts).strip()
    title = task.strip()[:80] or "演示文稿"

    json_slides = _parse_json_slides(combined)
    if json_slides:
        return {"title": title, "slides": json_slides[:max_slides]}

    slides: list[dict[str, Any]] = [{"title": title, "bullets": ["汇报主题", task[:120]]}]
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
            slides.append({"title": clean_title[:60], "bullets": bullets[:6]})
    elif combined:
        paragraphs = [p.strip() for p in combined.split("\n\n") if p.strip()]
        for idx, para in enumerate(paragraphs[: max_slides - 1]):
            bullets = _extract_bullets(para) or [para[:150]]
            slides.append({"title": f"要点 {idx + 1}", "bullets": bullets[:6]})

    if len(slides) <= 1 and combined:
        slides.append(
            {
                "title": "详细内容",
                "bullets": [combined[i : i + 120] for i in range(0, min(len(combined), 600), 120)],
            }
        )

    return {"title": title, "slides": slides[:max_slides]}
