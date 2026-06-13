"""
PPT 五维专项审核服务：量化评分、结构化报告、精准打回。
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

PASS_SCORE = 80
MAX_REJECT_ROUNDS = 3

# 五维权重（满分 100）
DIMENSION_WEIGHTS: dict[str, int] = {
    "content_quality": 35,
    "structure_logic": 25,
    "layout_professional": 20,
    "visualization": 10,
    "compliance": 10,
}

DIMENSION_LABELS: dict[str, str] = {
    "content_quality": "内容质量",
    "structure_logic": "结构逻辑",
    "layout_professional": "排版专业度",
    "visualization": "可视化效果",
    "compliance": "合规性",
}

# 八大必备模块关键词
REQUIRED_MODULES: list[tuple[str, list[str]]] = [
    ("cover", ["cover", "封面"]),
    ("toc", ["toc", "目录"]),
    ("background", ["背景", "现状", "情境", "background", "scqa"]),
    ("problem", ["问题", "目标", "冲突", "problem", "goal"]),
    ("solution", ["方案", "分析", "solution", "analysis", "核心"]),
    ("data", ["数据", "图表", "data", "chart", "指标"]),
    ("summary", ["总结", "建议", "结论", "summary", "recommend"]),
    ("ending", ["ending", "谢谢", "致谢", "q&a", "结尾"]),
]

MIN_PAGES: dict[str, int] = {"simple": 8, "medium": 12, "complex": 18}

HOLLOW_PHRASES = ["赋能", "抓手", "闭环", "打通", "沉淀", "对齐", "拉通", "颗粒度"]

REJECT_ROLE_MAP: dict[str, str] = {
    "content_quality": "copywriter",
    "structure_logic": "copywriter",
    "layout_professional": "ppt_designer",
    "visualization": "analyst",
    "compliance": "compliance_officer",
    "outline": "copywriter",
    "content": "analyst",
    "data": "analyst",
    "research": "researcher",
}


def _grade_from_score(score: float) -> str:
    if score >= 90:
        return "excellent"
    if score >= 80:
        return "good"
    if score >= 60:
        return "acceptable"
    return "reject"


def _grade_label(grade: str) -> str:
    return {
        "excellent": "优秀",
        "good": "良好",
        "acceptable": "合格",
        "reject": "不合格",
    }.get(grade, grade)


def _parse_outline_from_deliverables(
    deliverables: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """从交付物中提取 JSON 大纲。"""
    for item in deliverables:
        content = str(item.get("content") or "")
        for candidate in (content,):
            fence = re.search(r"```(?:json)?\s*([\s\S]*?)```", candidate)
            text = fence.group(1).strip() if fence else candidate.strip()
            try:
                data = json.loads(text)
                if isinstance(data, dict) and data.get("slides"):
                    return data
            except json.JSONDecodeError:
                start, end = text.find("{"), text.rfind("}")
                if start >= 0 and end > start:
                    try:
                        data = json.loads(text[start : end + 1])
                        if isinstance(data, dict) and data.get("slides"):
                            return data
                    except json.JSONDecodeError:
                        continue
    return None


def _slide_modules(outline: dict[str, Any]) -> set[str]:
    """识别大纲中已覆盖的模块。"""
    found: set[str] = set()
    slides = outline.get("slides") or []
    for slide in slides:
        if not isinstance(slide, dict):
            continue
        slide_type = str(slide.get("slide_type") or slide.get("type") or "").lower()
        title = str(slide.get("title") or "").lower()
        combined = f"{slide_type} {title}"
        for module_key, keywords in REQUIRED_MODULES:
            if any(kw in combined for kw in keywords):
                found.add(module_key)
    return found


def _count_content_slides(outline: dict[str, Any]) -> int:
    slides = outline.get("slides") or []
    return len([s for s in slides if isinstance(s, dict)])


def _check_bullets_quality(outline: dict[str, Any]) -> list[dict[str, Any]]:
    """检查每页要点质量（6x6、空洞套话）。"""
    issues: list[dict[str, Any]] = []
    for idx, slide in enumerate(outline.get("slides") or [], start=1):
        if not isinstance(slide, dict):
            continue
        slide_type = str(slide.get("slide_type") or "content").lower()
        if slide_type in ("cover", "toc", "ending", "section"):
            continue
        bullets = slide.get("bullets") or slide.get("points") or []
        if not isinstance(bullets, list):
            continue
        if len(bullets) > 6:
            issues.append(
                {
                    "page": idx,
                    "issue": f"第{idx}页要点超过6条，违反6x6原则",
                    "suggestion": "精简为不超过6条核心要点",
                    "assignee": "ppt_designer",
                }
            )
        for bullet in bullets:
            text = str(bullet)
            words = re.findall(r"[\u4e00-\u9fff\w]+", text)
            if len(words) > 6:
                issues.append(
                    {
                        "page": idx,
                        "issue": f"第{idx}页存在过长要点",
                        "suggestion": "每行不超过6个核心词",
                        "assignee": "ppt_designer",
                    }
                )
            if any(phrase in text for phrase in HOLLOW_PHRASES):
                issues.append(
                    {
                        "page": idx,
                        "issue": f"第{idx}页存在空洞套话「{text[:20]}」",
                        "suggestion": "替换为具体可验证的表述",
                        "assignee": "copywriter",
                    }
                )
            if len(text.strip()) < 8 and slide_type == "content":
                issues.append(
                    {
                        "page": idx,
                        "issue": f"第{idx}页内容过于空洞",
                        "suggestion": "补充论点+论据+数据",
                        "assignee": "copywriter",
                    }
                )
    return issues


def _build_report(
    *,
    audit_type: str,
    scores: dict[str, float],
    issues: list[dict[str, Any]],
    passed: bool,
    assignee: str,
    summary: str,
) -> dict[str, Any]:
    total = round(sum(scores.values()), 1)
    grade = _grade_from_score(total)
    dimension_scores = {
        key: {
            "label": DIMENSION_LABELS[key],
            "score": round(scores.get(key, 0), 1),
            "max": DIMENSION_WEIGHTS[key],
        }
        for key in DIMENSION_WEIGHTS
    }
    return {
        "audit_type": audit_type,
        "passed": passed,
        "total_score": total,
        "grade": grade,
        "grade_label": _grade_label(grade),
        "dimension_scores": dimension_scores,
        "issues": issues,
        "suggestions": [i.get("suggestion", "") for i in issues if i.get("suggestion")],
        "assignee": assignee,
        "summary": summary,
        "pass_threshold": PASS_SCORE,
    }


class PptAuditService:
    """PPT 专项审核：大纲 / 内容 / 终稿三卡点 + 五维终评。"""

    def audit_outline(
        self,
        outline: dict[str, Any] | None,
        *,
        complexity: str = "medium",
        deliverables: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """大纲审核卡点：结构完整性、逻辑性、页数、观点明确性。"""
        if outline is None and deliverables:
            outline = _parse_outline_from_deliverables(deliverables)
        if not outline or not outline.get("slides"):
            return _build_report(
                audit_type="outline",
                scores={k: 0 for k in DIMENSION_WEIGHTS},
                issues=[
                    {
                        "page": 0,
                        "issue": "未找到结构化 PPT 大纲（需 JSON slides）",
                        "suggestion": "输出含 cover/toc/content/ending 的完整 JSON 大纲",
                        "assignee": "copywriter",
                    }
                ],
                passed=False,
                assignee="copywriter",
                summary="大纲缺失，无法进入内容生产阶段",
            )

        issues: list[dict[str, Any]] = []
        modules = _slide_modules(outline)
        missing = [m for m, _ in REQUIRED_MODULES if m not in modules]
        for mod in missing:
            mod_label = next(l for k, l in REQUIRED_MODULES if k == mod)
            issues.append(
                {
                    "page": 0,
                    "issue": f"缺少必备模块：{mod_label}",
                    "suggestion": f"补充{mod_label}相关页面",
                    "assignee": "copywriter",
                }
            )

        min_pages = MIN_PAGES.get(complexity, 12)
        page_count = _count_content_slides(outline)
        if page_count < min_pages:
            issues.append(
                {
                    "page": 0,
                    "issue": f"页数不足（当前{page_count}页，要求≥{min_pages}页）",
                    "suggestion": "按 SCQA 结构扩展背景、方案、数据、总结等章节",
                    "assignee": "copywriter",
                }
            )

        issues.extend(_check_bullets_quality(outline))

        # 结构逻辑分
        structure_score = max(0, 25 - len(missing) * 5 - max(0, min_pages - page_count))
        content_score = max(0, 35 - len([i for i in issues if "空洞" in i.get("issue", "")]) * 5)
        compliance_score = 10.0
        layout_score = 15.0
        viz_score = 8.0

        scores = {
            "content_quality": float(content_score),
            "structure_logic": float(structure_score),
            "layout_professional": float(layout_score),
            "visualization": float(viz_score),
            "compliance": float(compliance_score),
        }
        total = sum(scores.values())
        passed = total >= PASS_SCORE and not missing
        assignee = "copywriter" if not passed else "auditor"
        summary = (
            f"大纲审核{'通过' if passed else '不通过'}（{total:.0f}分），"
            f"覆盖模块 {len(modules)}/8，共 {page_count} 页"
        )
        return _build_report(
            audit_type="outline",
            scores=scores,
            issues=issues,
            passed=passed,
            assignee=assignee,
            summary=summary,
        )

    def audit_content(
        self,
        outline: dict[str, Any] | None,
        deliverables: list[dict[str, Any]],
        *,
        complexity: str = "medium",
    ) -> dict[str, Any]:
        """内容审核卡点：事实支撑、论据充分、逻辑一致。"""
        if outline is None:
            outline = _parse_outline_from_deliverables(deliverables)
        issues: list[dict[str, Any]] = []

        combined_text = " ".join(
            str(d.get("content") or "") for d in deliverables
        ).lower()
        has_source = any(
            kw in combined_text
            for kw in ("来源", "source", "引用", "据", "数据来自", "参考")
        )
        if not has_source:
            issues.append(
                {
                    "page": 0,
                    "issue": "内容未标注数据来源",
                    "suggestion": "关键数据需标注来源（知识库/检索/计算过程）",
                    "assignee": "analyst",
                }
            )

        data_slides = 0
        chart_slides = 0
        if outline:
            for idx, slide in enumerate(outline.get("slides") or [], start=1):
                if not isinstance(slide, dict):
                    continue
                title = str(slide.get("title") or "")
                if any(kw in title for kw in ("数据", "指标", "趋势", "对比")):
                    data_slides += 1
                    if not slide.get("chart") and not slide.get("table"):
                        issues.append(
                            {
                                "page": idx,
                                "issue": f"第{idx}页「{title}」缺少图表或表格",
                                "suggestion": "补充 bar/line/pie 图表或数据表格",
                                "assignee": "analyst",
                            }
                        )
                    else:
                        chart_slides += 1
                bullets = slide.get("bullets") or []
                for bullet in bullets:
                    text = str(bullet)
                    if len(text) < 15 and "content" in str(slide.get("slide_type", "")):
                        issues.append(
                            {
                                "page": idx,
                                "issue": f"第{idx}页论据不足：「{text[:30]}」",
                                "suggestion": "补充论点+论据+数据结构",
                                "assignee": "analyst",
                            }
                        )

        content_score = max(0, 35 - len(issues) * 4)
        structure_score = 22.0
        layout_score = 18.0
        viz_score = max(0, 10 - (data_slides - chart_slides) * 5)
        compliance_score = 10.0 if has_source else 5.0

        scores = {
            "content_quality": float(content_score),
            "structure_logic": float(structure_score),
            "layout_professional": float(layout_score),
            "visualization": float(viz_score),
            "compliance": float(compliance_score),
        }
        total = sum(scores.values())
        passed = total >= PASS_SCORE and compliance_score >= 8
        assignee = issues[0].get("assignee", "analyst") if issues else "ppt_designer"
        summary = f"内容审核{'通过' if passed else '不通过'}（{total:.0f}分）"
        return _build_report(
            audit_type="content",
            scores=scores,
            issues=issues,
            passed=passed,
            assignee=assignee,
            summary=summary,
        )

    def audit_final(
        self,
        *,
        task: str,
        deliverables: list[dict[str, Any]],
        results: dict[str, Any],
        outline: dict[str, Any] | None = None,
        ppt_file: dict[str, Any] | None = None,
        complexity: str = "medium",
        llm_invoke: Optional[Callable[[str], str]] = None,
    ) -> dict[str, Any]:
        """终稿五维专项审核（PPT 任务默认使用，替代通用四维审核）。"""
        if outline is None:
            outline = _parse_outline_from_deliverables(deliverables)

        outline_report = self.audit_outline(outline, complexity=complexity)
        content_report = self.audit_content(outline, deliverables, complexity=complexity)
        issues: list[dict[str, Any]] = list(outline_report.get("issues") or [])
        issues.extend(content_report.get("issues") or [])

        layout_score = 20.0
        if ppt_file:
            slide_count = int(ppt_file.get("slide_count") or 0)
            if slide_count < MIN_PAGES.get(complexity, 12):
                issues.append(
                    {
                        "page": 0,
                        "issue": f"生成 PPT 仅 {slide_count} 页，未达最低要求",
                        "suggestion": "扩展内容后重新排版生成",
                        "assignee": "ppt_designer",
                    }
                )
                layout_score -= 10
        else:
            issues.append(
                {
                    "page": 0,
                    "issue": "未生成 PPTX 文件",
                    "suggestion": "PPT 设计师需调用 generate_ppt 生成文件",
                    "assignee": "ppt_designer",
                }
            )
            layout_score = 5.0

        issues.extend(_check_bullets_quality(outline or {}))

        # 合并维度得分
        scores = {
            "content_quality": min(
                35.0,
                (outline_report["dimension_scores"]["content_quality"]["score"]
                 + content_report["dimension_scores"]["content_quality"]["score"])
                / 2,
            ),
            "structure_logic": outline_report["dimension_scores"]["structure_logic"]["score"],
            "layout_professional": layout_score,
            "visualization": content_report["dimension_scores"]["visualization"]["score"],
            "compliance": content_report["dimension_scores"]["compliance"]["score"],
        }

        # 可选 LLM 增强终评
        if llm_invoke and outline:
            try:
                prompt = f"""
你是 PPT 质量审核专家，请对以下演示文稿进行五维评分（满分100：内容35+结构25+排版20+可视化10+合规10）。

任务：{task}
页数：{len(outline.get('slides') or [])}
大纲摘要：{json.dumps(outline.get('slides', [])[:5], ensure_ascii=False)[:1500]}

请仅输出 JSON：
{{"content_quality":0-35,"structure_logic":0-25,"layout_professional":0-20,"visualization":0-10,"compliance":0-10,"issues":[{{"page":1,"issue":"","suggestion":"","assignee":"copywriter"}}],"summary":""}}
"""
                raw = llm_invoke(prompt)
                start, end = raw.find("{"), raw.rfind("}")
                if start >= 0 and end > start:
                    parsed = json.loads(raw[start : end + 1])
                    for key in DIMENSION_WEIGHTS:
                        val = parsed.get(key)
                        if isinstance(val, (int, float)):
                            scores[key] = min(float(val), float(DIMENSION_WEIGHTS[key]))
                    llm_issues = parsed.get("issues") or []
                    if isinstance(llm_issues, list):
                        issues.extend([i for i in llm_issues if isinstance(i, dict)])
            except Exception as exc:
                logger.warning("PPT 终评 LLM 增强失败: %s", exc)

        total = round(sum(scores.values()), 1)
        passed = total >= PASS_SCORE
        grade = _grade_from_score(total)
        assignee = "ppt_designer"
        if issues:
            assignee = str(issues[0].get("assignee") or REJECT_ROLE_MAP.get(
                min(scores, key=scores.get), "copywriter"
            ))

        return {
            "passed": passed,
            "grade": grade,
            "grade_label": _grade_label(grade),
            "total_score": total,
            "pass_threshold": PASS_SCORE,
            "dimension_scores": {
                key: {
                    "label": DIMENSION_LABELS[key],
                    "score": round(scores[key], 1),
                    "max": DIMENSION_WEIGHTS[key],
                }
                for key in DIMENSION_WEIGHTS
            },
            "issues": [i.get("issue", str(i)) if isinstance(i, dict) else str(i) for i in issues[:10]],
            "issue_details": issues[:15],
            "suggestions": list(
                dict.fromkeys(
                    i.get("suggestion", "")
                    for i in issues
                    if isinstance(i, dict) and i.get("suggestion")
                )
            )[:8],
            "assignee": assignee,
            "summary": f"PPT 五维专项审核{'通过' if passed else '不通过'}，综合得分 {total:.0f} 分（{_grade_label(grade)}）",
            "audit_type": "final",
            "dimensions": {k: scores[k] >= DIMENSION_WEIGHTS[k] * 0.6 for k in scores},
            "audit_records": [
                {
                    "dimension": k,
                    "label": DIMENSION_LABELS[k],
                    "score": round(scores[k], 1),
                    "max": DIMENSION_WEIGHTS[k],
                    "passed": scores[k] >= DIMENSION_WEIGHTS[k] * 0.6,
                }
                for k in DIMENSION_WEIGHTS
            ],
        }


ppt_audit_service = PptAuditService()
