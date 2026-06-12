"""
群聊协同子任务辅助函数（供统一工作流引擎复用）。
"""

from __future__ import annotations

from typing import Any, Optional

from app.services.workflow.nodes.constants import AGENT_ROLES, SUBTASK_ROLE_MAP


def enrich_subtasks_with_roles(
    raw_subtasks: list[dict[str, Any]],
    task: str,
) -> list[dict[str, Any]]:
    """将调度拆解结果转换为带群聊角色的子任务列表。"""
    subtasks: list[dict[str, Any]] = []
    for idx, item in enumerate(raw_subtasks):
        agent_type = item.get("agent", "search")
        role = SUBTASK_ROLE_MAP.get(agent_type, "analyst")
        subtasks.append(
            {
                "id": f"subtask_{idx + 1}",
                "agent": agent_type,
                "role": role,
                "task": item.get("task", task),
                "status": "pending",
            }
        )
    if not subtasks:
        subtasks.append(
            {
                "id": "subtask_1",
                "agent": "search",
                "role": "researcher",
                "task": task,
                "status": "pending",
            }
        )
    if not any(s.get("role") == "analyst" for s in subtasks):
        subtasks.append(
            {
                "id": f"subtask_{len(subtasks) + 1}",
                "agent": "analysis",
                "role": "analyst",
                "task": f"基于已有资料汇总并生成分析报告：{task}",
                "status": "pending",
            }
        )
    return subtasks


def get_pending_subtask(subtasks: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    """获取下一个待执行子任务。"""
    for subtask in subtasks:
        if subtask.get("status") != "completed":
            return subtask
    return None


def mark_subtask_completed(subtasks: list[dict[str, Any]], subtask_id: str) -> None:
    """标记子任务完成。"""
    for subtask in subtasks:
        if subtask.get("id") == subtask_id:
            subtask["status"] = "completed"
            break


def calc_group_chat_progress(
    subtasks: list[dict[str, Any]],
    status: str,
    base_progress: float = 0.0,
) -> float:
    """计算群聊整体进度百分比。"""
    if not subtasks:
        return base_progress
    completed = sum(1 for t in subtasks if t.get("status") == "completed")
    base = (completed / len(subtasks)) * 80
    if status == "reviewing":
        return min(base + 10, 90)
    if status == "completed":
        return 100.0
    return min(base, 80.0)


def build_final_answer(
    task: str,
    deliverables: list[dict[str, Any]],
    review_result: dict[str, Any] | None,
) -> str:
    """汇总最终交付物为报告文本。"""
    parts = [f"# 任务交付报告\n\n**任务**：{task}\n"]
    for item in deliverables:
        role_name = AGENT_ROLES.get(item.get("role", ""), {}).get("name", "成员")
        parts.append(f"\n## {role_name}交付\n\n{item.get('content', '')}")
    review = review_result or {}
    parts.append(f"\n\n---\n**审核结论**：{review.get('summary', '通过')}")
    return "\n".join(parts)
