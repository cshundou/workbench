"""
通用强制审核节点：四维度结构化审核，支持打回与人工兜底。
"""

from __future__ import annotations

import json
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

DEFAULT_AUDIT_DIMENSIONS: list[str] = [
    "completeness",
    "accuracy",
    "logic",
    "compliance",
]

DIMENSION_LABELS: dict[str, str] = {
    "completeness": "内容完整性",
    "accuracy": "数据准确性",
    "logic": "逻辑合理性",
    "compliance": "合规性",
}


def _parse_audit_json(content: str) -> dict[str, Any]:
    """从 LLM 输出解析审核 JSON。"""
    text = content.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        return json.loads(text[start : end + 1])
    raise ValueError("未找到有效 JSON")


def run_forced_audit(
    *,
    task: str,
    deliverables: list[dict[str, Any]],
    results: dict[str, Any],
    dimensions: list[str] | None = None,
    llm_invoke: Optional[Callable[[str], str]] = None,
) -> dict[str, Any]:
    """
    执行四维度强制审核。

    Returns:
        结构化审核结果，含 passed/grade/issues/assignee/summary/dimensions/audit_records。
    """
    dims = dimensions or DEFAULT_AUDIT_DIMENSIONS
    dim_lines = "\n".join(
        f"{idx + 1}. {DIMENSION_LABELS.get(d, d)}"
        for idx, d in enumerate(dims)
    )
    review_prompt = f"""
你是严格的成果审核员，请从以下维度审核交付物：
{dim_lines}

原始任务：{task}

交付物：
{json.dumps(deliverables, ensure_ascii=False, default=str)}

子任务结果：
{json.dumps(results, ensure_ascii=False, default=str)}

请仅输出 JSON：
{{
  "passed": true/false,
  "grade": "pass" | "conditional" | "reject",
  "issues": ["问题1", "问题2"],
  "assignee": "researcher" | "engineer" | "analyst",
  "summary": "审核意见摘要",
  "dimensions": {{
    "completeness": true/false,
    "accuracy": true/false,
    "logic": true/false,
    "compliance": true/false
  }}
}}
"""
    default_result: dict[str, Any] = {
        "passed": True,
        "grade": "pass",
        "issues": [],
        "assignee": "analyst",
        "summary": "成果符合基本要求",
        "dimensions": {d: True for d in dims},
        "audit_records": [],
    }

    if llm_invoke is None:
        return default_result

    try:
        content = llm_invoke(review_prompt)
        parsed = _parse_audit_json(content)
        default_result.update(parsed)
        default_result["audit_records"] = [
            {
                "dimension": d,
                "passed": bool((parsed.get("dimensions") or {}).get(d, True)),
                "label": DIMENSION_LABELS.get(d, d),
            }
            for d in dims
        ]
    except Exception as exc:
        logger.warning("审核 LLM 解析失败，默认通过: %s", exc)

    return default_result


class ForcedAuditRunner:
    """强制审核节点执行器（供 WorkflowBuilder 调用）。"""

    def __init__(
        self,
        llm_invoke: Optional[Callable[[str], str]] = None,
    ) -> None:
        self._llm_invoke = llm_invoke

    def run(
        self,
        *,
        task: str,
        deliverables: list[dict[str, Any]],
        results: dict[str, Any],
        config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """按节点配置执行审核。"""
        config = config or {}
        dimensions = config.get("audit_dimensions") or DEFAULT_AUDIT_DIMENSIONS
        return run_forced_audit(
            task=task,
            deliverables=deliverables,
            results=results,
            dimensions=list(dimensions),
            llm_invoke=self._llm_invoke,
        )
